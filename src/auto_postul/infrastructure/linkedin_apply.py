"""Automatización asistida de Easy Apply con Patchright.

Principio de seguridad: completa, revisa y se detiene. Nunca hace clic en
"Enviar solicitud" si el modo live no está habilitado y confirmado.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from auto_postul.config import Settings
from auto_postul.domain.schemas import FormField, PrepareResult, SubmitResult

logger = logging.getLogger(__name__)

EASY_APPLY_LABELS = re.compile(
    r"easy apply|solicitud sencilla|postularme|solicitar|aplicar|apply",
    re.IGNORECASE,
)
NEXT_LABELS = re.compile(r"next|siguiente|continue|continuar|review|revisar", re.IGNORECASE)
SUBMIT_LABELS = re.compile(
    r"submit application|enviar solicitud|enviar postulación|submit|enviar",
    re.IGNORECASE,
)
SUCCESS_MARKERS = (
    "application submitted",
    "solicitud enviada",
    "your application was sent",
    "tu solicitud se envió",
    "postulación enviada",
    "application sent",
)
ERROR_MARKERS = (
    "please enter",
    "required",
    "obligatorio",
    "revisa",
    "enter a valid",
    "selecciona",
)


@dataclass(slots=True)
class ApplyContext:
    application_id: str
    job_url: str
    candidate: dict[str, str]
    answers: dict[str, str]
    resume_path: Path
    settings: Settings


@dataclass(slots=True)
class OpenSession:
    playwright: Any
    context: Any
    page: Any
    context_data: ApplyContext


_OPEN_SESSIONS: dict[str, OpenSession] = {}
_PREVIEW_TASKS: dict[str, asyncio.Task[None]] = {}
_LOCK = asyncio.Lock()


async def prepare_application(context: ApplyContext) -> PrepareResult:
    """Abre la oferta, completa los pasos y se detiene en revisión."""
    async with _LOCK:
        await close_application(context.application_id)
        playwright = None
        browser_context = None
        try:
            from patchright.async_api import async_playwright

            playwright = await async_playwright().start()
            browser_context = await _launch_context(playwright, context.settings)
            page = (
                browser_context.pages[0]
                if browser_context.pages
                else await browser_context.new_page()
            )
            page.set_default_timeout(20_000)
            _start_live_preview(context.application_id, page, context.settings)
            await page.goto(context.job_url, wait_until="domcontentloaded", timeout=60_000)
            await _pause(context.settings)
            await _assert_logged_in(page)
            await _assert_not_applied(page)

            page = await _click_easy_apply(page)
            await _pause(context.settings)
            dialog = await _wait_apply_form(page)

            fields: list[FormField] = []
            for step in range(1, context.settings.apply_max_steps + 1):
                raw_fields = await _extract_fields(dialog, step)
                if raw_fields:
                    resolved = _resolve_fields(raw_fields, context)
                    fields.extend(resolved)
                    await _fill_fields(dialog, resolved, context, step)
                    await _pause(context.settings)

                if await _on_review(page, dialog):
                    break
                errors = await _visible_errors(page)
                if errors:
                    return await _finish_with_screenshot(
                        page,
                        context,
                        fields,
                        "needs_input",
                        "El formulario muestra errores de validación: " + " | ".join(errors[:3]),
                        browser_context,
                        playwright,
                    )
                moved = await _click_next(page, dialog)
                if not moved:
                    break
                await _pause(context.settings)

            unresolved = [field for field in fields if field.required and field.status == "pending"]
            status = "needs_input" if unresolved else "ready_for_review"
            message = (
                "Faltan datos obligatorios. Revisá el banco de respuestas y reintentá."
                if unresolved
                else "Formulario completo. Revisá y confirmá el envío."
            )
            result = await _finish_with_screenshot(
                page, context, fields, status, message, browser_context, playwright, keep_open=True
            )
            _OPEN_SESSIONS[context.application_id] = OpenSession(
                playwright=playwright,
                context=browser_context,
                page=page,
                context_data=context,
            )
            return result
        except Exception as exc:
            _stop_live_preview(context.application_id)
            screenshot = ""
            if browser_context is not None:
                try:
                    if browser_context.pages:
                        screenshot = await _screenshot(
                            browser_context.pages[0],
                            context.settings,
                            context.application_id,
                            "error",
                        )
                except Exception:
                    logger.debug("No se pudo guardar la captura de error", exc_info=True)
                await _safe_close(browser_context)
            if playwright is not None:
                await _safe_stop(playwright)
            logger.exception("Falló la preparación de Easy Apply")
            return PrepareResult(
                status="failed",
                fields=[],
                message=f"No se pudo preparar la postulación: {exc}",
                screenshot=screenshot,
            )


async def submit_application(application_id: str, settings: Settings) -> SubmitResult:
    """Hace clic en enviar solo si el modo live está explícitamente habilitado."""
    session = _OPEN_SESSIONS.get(application_id)
    if session is None:
        return SubmitResult(
            status="failed",
            message="La preparación expiró. Volvé a preparar el formulario antes de enviar.",
        )
    if settings.apply_dry_run or not settings.apply_live_submit:
        return SubmitResult(
            status="dry_run",
            message="Modo seguro activo: no se envió nada. Revisá el formulario en el navegador.",
            confirmed=False,
        )
    page = session.page
    try:
        button = page.get_by_role("button", name=SUBMIT_LABELS)
        if await button.count() == 0:
            button = page.get_by_text(SUBMIT_LABELS)
        if await button.count() == 0:
            return SubmitResult(status="failed", message="No encontré el botón de envío.")
        await button.first.click()
        await _pause(settings)
        await asyncio.sleep(2)
        text = (await page.locator("body").inner_text())[:20000]
        screenshot = await _screenshot(page, settings, application_id, "submitted")
        if any(marker in text.casefold() for marker in SUCCESS_MARKERS):
            await close_application(application_id)
            return SubmitResult(
                status="submitted",
                message="LinkedIn confirmó el envío.",
                screenshot=screenshot,
                confirmed=True,
            )
        await close_application(application_id)
        return SubmitResult(
            status="submission_unknown",
            message="Hice clic en enviar pero no pude verificar la confirmación. Revisá LinkedIn manualmente.",
            screenshot=screenshot,
            confirmed=False,
        )
    except Exception as exc:
        logger.exception("Falló el envío de la postulación")
        return SubmitResult(status="failed", message=f"No se pudo enviar: {exc}")


async def close_application(application_id: str) -> None:
    _stop_live_preview(application_id)
    session = _OPEN_SESSIONS.pop(application_id, None)
    if session is None:
        return
    await _safe_close(session.context)
    await _safe_stop(session.playwright)


def live_preview_paths(settings: Settings, application_id: str) -> tuple[Path, Path]:
    """Rutas de la captura y metadatos del proceso en vivo."""
    return (
        settings.artifacts_dir / f"live-{application_id}.png",
        settings.artifacts_dir / f"live-{application_id}.json",
    )


def _start_live_preview(application_id: str, page: Any, settings: Settings) -> None:
    """Captura el navegador cada dos segundos para el panel."""
    _stop_live_preview(application_id)
    task = asyncio.create_task(_live_preview_loop(application_id, page, settings))
    _PREVIEW_TASKS[application_id] = task


def _stop_live_preview(application_id: str) -> None:
    task = _PREVIEW_TASKS.pop(application_id, None)
    if task is not None and not task.done():
        task.cancel()


async def _live_preview_loop(application_id: str, page: Any, settings: Settings) -> None:
    image_path, meta_path = live_preview_paths(settings, application_id)
    while True:
        try:
            if page.is_closed():
                break
            await page.screenshot(path=str(image_path), animations="disabled")
            payload = {
                "application_id": application_id,
                "url": page.url,
                "title": await page.title(),
                "updated_at": datetime.now(UTC).isoformat(),
            }
            meta_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except asyncio.CancelledError:
            raise
        except Exception:
            # Durante una navegación la captura puede fallar; se reintenta.
            pass
        await asyncio.sleep(2)


def live_preview_snapshot(settings: Settings, application_id: str) -> dict[str, Any] | None:
    """Lee la última captura de una postulación, si existe."""
    image_path, meta_path = live_preview_paths(settings, application_id)
    if not image_path.exists() or not meta_path.exists():
        return None
    try:
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    payload["image"] = image_path
    try:
        updated = datetime.fromisoformat(str(payload.get("updated_at", "")))
        payload["age_seconds"] = max(0.0, (datetime.now(UTC) - updated).total_seconds())
    except Exception:
        payload["age_seconds"] = 9999.0
    return payload


def latest_live_preview(settings: Settings) -> dict[str, Any] | None:
    """Devuelve la captura más reciente entre todas las postulaciones."""
    files = sorted(
        settings.artifacts_dir.glob("live-*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for meta in files[:10]:
        application_id = meta.stem.removeprefix("live-")
        snapshot = live_preview_snapshot(settings, application_id)
        if snapshot is not None:
            return snapshot
    return None


async def _launch_context(playwright: Any, settings: Settings) -> Any:
    kwargs: dict[str, Any] = {
        "user_data_dir": str(settings.linkedin_profile_dir),
        "headless": settings.apply_headless,
        "slow_mo": 120,
    }
    if settings.apply_headless:
        kwargs["viewport"] = {"width": 1280, "height": 900}
    try:
        return await playwright.chromium.launch_persistent_context(channel="chromium", **kwargs)
    except Exception:
        logger.warning("No se pudo abrir Chromium con channel=chromium; reintentando sin channel")
        return await playwright.chromium.launch_persistent_context(**kwargs)


async def _pause(settings: Settings) -> None:
    base = max(0.0, settings.apply_action_delay_ms / 1000)
    jitter = random.uniform(0.0, max(0.0, settings.apply_action_delay_jitter_ms / 1000))
    await asyncio.sleep(base + jitter)


async def _assert_logged_in(page: Any) -> None:
    url = page.url.casefold()
    if "/login" in url or "checkpoint" in url or "authwall" in url:
        raise RuntimeError("LinkedIn pidió login o verificación. Iniciá sesión desde Ajustes.")
    text = (await page.locator("body").inner_text())[:5000].casefold()
    if any(
        marker in text
        for marker in (
            "captcha",
            "verificación de seguridad",
            "verificacion de seguridad",
            "unusual activity",
            "actividad inusual",
            "rate limit",
            "demasiadas solicitudes",
            "too many requests",
        )
    ):
        raise RuntimeError(
            "LinkedIn pidió CAPTCHA, verificación o rate limit. La automatización se detuvo."
        )
    if "sign in" in text and "linkedin" in text and "feed" not in url:
        raise RuntimeError("La sesión de LinkedIn no está activa.")


async def _assert_not_applied(page: Any) -> None:
    text = (await page.locator("body").inner_text())[:12000].casefold()
    for heading in ("acerca del empleo", "about the job", "descripción del puesto"):
        index = text.find(heading)
        if index != -1:
            text = text[:index]
            break
    markers = (
        "solicitud enviada",
        "application submitted",
        "ya te postulaste",
        "already applied",
        "no longer accepting applications",
        "ya no acepta solicitudes",
    )
    if any(marker in text for marker in markers):
        raise RuntimeError("La oferta ya fue aplicada o está cerrada.")


async def _click_easy_apply(page: Any) -> Any:
    before_pages = set(page.context.pages)
    candidates = [
        page.locator('a[href*="/apply/"]:visible'),
        page.locator('[aria-label*="Easy Apply" i]:visible'),
        page.get_by_role("button", name=EASY_APPLY_LABELS),
        page.get_by_role("link", name=EASY_APPLY_LABELS),
    ]
    for locator in candidates:
        try:
            if await locator.count() > 0:
                await locator.first.click()
                await asyncio.sleep(1.5)
                new_pages = [item for item in page.context.pages if item not in before_pages]
                if new_pages:
                    return new_pages[-1]
                return page
        except Exception:
            continue
    raise RuntimeError("No encontré el botón de Easy Apply. Puede que la oferta ya no lo tenga.")


async def _wait_apply_form(page: Any) -> Any:
    """Devuelve el modal o el body de la página completa de Easy Apply."""
    selectors = [
        '[data-view-name="unified-apply"]',
        '[role="dialog"]',
        ".jobs-easy-apply-modal",
        "div[data-test-modal]",
        "div[aria-modal='true']",
    ]
    for _ in range(24):
        for selector in selectors:
            locator = page.locator(selector).first
            try:
                if await locator.count() > 0 and await locator.is_visible():
                    return locator
            except Exception:
                continue
        try:
            body_text = (await page.locator("body").inner_text())[:4000].casefold()
            is_apply_page = (
                "companyname=" in page.url.casefold()
                or "aplicar a" in body_text
                or "contact info" in body_text
                or "información de contacto" in body_text
            )
            has_fields = await page.locator("input, select, textarea").count() > 0
            if is_apply_page and has_fields:
                return page.locator("body")
        except Exception:
            pass
        await asyncio.sleep(0.5)
    body = (await page.locator("body").inner_text())[:500].replace("\n", " ")
    raise RuntimeError(f"No se abrió el formulario de Easy Apply. URL: {page.url}. Texto: {body}")


EXTRACT_FIELDS_JS = r"""
(root) => {
  const dialog = root || document;
  const fields = [];
  const nodes = [...dialog.querySelectorAll('input, select, textarea, [role="combobox"]')];
  const seen = new Set();
  const textOf = (node) => {
    if (!node) return '';
    return (node.innerText || node.textContent || '').trim().replace(/\s+/g, ' ');
  };
  for (const node of nodes) {
    const type = (node.getAttribute('type') || node.tagName || '').toLowerCase();
    if (['hidden', 'submit', 'button', 'reset'].includes(type)) continue;
    const key = node.id || node.getAttribute('name') || node.getAttribute('aria-label') || '';
    if (!key || seen.has(key)) continue;
    seen.add(key);
    const id = node.id;
    const labelNode = id ? dialog.querySelector(`label[for="${CSS.escape(id)}"]`) : null;
    const wrapping = node.closest('label');
    const aria = node.getAttribute('aria-label') || '';
    const placeholder = node.getAttribute('placeholder') || '';
    const fallback = type === 'file' ? 'Currículum' : (node.getAttribute('name') || key);
    const label = (labelNode && textOf(labelNode)) || (wrapping && textOf(wrapping)) || aria || placeholder || fallback;
    const required = Boolean(node.required || node.getAttribute('aria-required') === 'true' ||
      (label.length < 120 && label.trim().endsWith('*')));
    const options = node.tagName === 'SELECT'
      ? [...node.options].map(o => (o.textContent || '').trim()).filter(Boolean)
      : [];
    fields.push({
      key: key,
      label: label,
      field_type: type === 'select' ? 'select' : (type || 'text'),
      required: Boolean(required),
      value: node.value || '',
      options: options,
      autocomplete: node.getAttribute('autocomplete') || '',
      name: node.getAttribute('name') || '',
    });
  }
  return fields;
}
"""


async def _extract_fields(dialog: Any, step: int) -> list[FormField]:
    raw = await dialog.evaluate(EXTRACT_FIELDS_JS)
    fields: list[FormField] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        field_type = str(item.get("field_type") or "text")
        if field_type in ("checkbox", "radio"):
            field_type = "choice"
        fields.append(
            FormField(
                key=str(item.get("key") or ""),
                label=str(item.get("label") or "")[:500],
                field_type=field_type,
                required=bool(item.get("required")),
                value=str(item.get("value") or ""),
                options=[str(value) for value in item.get("options", []) if value],
                step=step,
            )
        )
    return fields


def _resolve_fields(fields: list[FormField], context: ApplyContext) -> list[FormField]:
    answers = {key.casefold(): value for key, value in context.answers.items()}
    candidate = {key.casefold(): value for key, value in context.candidate.items()}
    for field in fields:
        value, source = _resolve_one(field, candidate, answers, context)
        field.source = source
        if value:
            field.value = value
            field.status = "resolved"
            field.confidence = 0.9 if source != "heuristica" else 0.6
        elif field.required:
            field.status = "pending"
        else:
            field.status = "skipped"
    return fields


def _english_option(value: str) -> str:
    """Mapea el nivel honesto del CV a las opciones de LinkedIn."""
    folded = value.casefold()
    if any(marker in folded for marker in ("native", "nativo", "bilingüe", "bilingue")):
        return "Native or bilingual"
    if any(marker in folded for marker in ("c1", "c2", "advanced", "avanzado", "fluent", "fluido")):
        return "Professional"
    if any(
        marker in folded for marker in ("b1", "b2", "intermediate", "intermedio", "conversational")
    ):
        return "Conversational"
    # A1/A2/básico: no inflar el nivel.
    return "None"


def _resolve_one(
    field: FormField,
    candidate: dict[str, str],
    answers: dict[str, str],
    context: ApplyContext,
) -> tuple[str, str]:
    label = f"{field.label} {field.key}".casefold()
    if field.field_type in ("file",):
        if context.resume_path.exists():
            return str(context.resume_path), "cv_original"
        return "", ""
    if "email" in label or "correo" in label:
        if field.field_type == "select" and field.value:
            return field.value, "linkedin_prefill"
        return candidate.get("email", ""), "perfil"
    if "phone" in label or "teléfono" in label or "telefono" in label:
        if field.value:
            return field.value, "linkedin_prefill"
        return candidate.get("phone", ""), "perfil"
    if "full name" in label or "nombre completo" in label:
        return candidate.get("full_name", ""), "perfil"
    if "first name" in label or ("nombre" in label and "apellido" not in label):
        return answers.get("first_name") or candidate.get("first_name", ""), "perfil"
    if "last name" in label or "apellido" in label:
        return answers.get("last_name") or candidate.get("last_name", ""), "perfil"
    if "linkedin" in label:
        return answers.get("linkedin", candidate.get("linkedin_url", "")), "perfil"
    if "github" in label:
        return answers.get("github", candidate.get("github_url", "")), "perfil"
    if "city" in label or "ciudad" in label or "location" in label or "ubicación" in label:
        return candidate.get("location", ""), "perfil"
    if "country" in label or "país" in label or "pais" in label or "código del país" in label:
        return answers.get("country", "") or candidate.get("location", ""), "banco"
    if "authorized" in label or "autoriz" in label or "work permit" in label:
        return answers.get("work_authorization", ""), "banco"
    if "sponsor" in label or "patrocin" in label:
        return answers.get("sponsorship", "No"), "banco"
    if "remote" in label or "remoto" in label:
        return answers.get("remote", "Sí"), "banco"
    if "english" in label or "inglés" in label or "ingles" in label:
        value = answers.get("english_level", "") or candidate.get("english_level", "")
        if field.field_type == "select":
            return _english_option(value), "banco"
        return value, "banco"
    if "years" in label or "años" in label:
        return candidate.get("years_experience", ""), "perfil"
    if (
        "salary" in label
        or "pretensión" in label
        or "pretension" in label
        or "compensación" in label
    ):
        return answers.get("salary_expectation", ""), "banco"
    if "notice" in label or "preaviso" in label:
        return answers.get("notice_period", ""), "banco"
    if "availability" in label or "disponibilidad" in label:
        return answers.get("availability", ""), "banco"
    if "why" in label or "por qué" in label or "porque" in label:
        return "", ""
    if "website" in label or "portfolio" in label:
        return candidate.get("portfolio_url", ""), "perfil"
    for key, value in answers.items():
        if key and key in label:
            return value, "banco"
    return "", ""


async def _fill_fields(
    dialog: Any, fields: list[FormField], context: ApplyContext, step: int
) -> None:
    for field in fields:
        if field.status != "resolved" or not field.value:
            continue
        locator = None
        try:
            if field.field_type == "file":
                locator = dialog.locator('input[type="file"]').first
                await locator.set_input_files(field.value)
                continue
            selector = f"[id={json.dumps(field.key)}]"
            locator = dialog.locator(selector).first
            if await locator.count() == 0:
                locator = dialog.locator(f"[name={json.dumps(field.key)}]").first
            if await locator.count() == 0:
                continue
            if field.field_type == "select":
                try:
                    await locator.select_option(label=field.value)
                except Exception:
                    try:
                        await locator.select_option(value=field.value)
                    except Exception:
                        options = await locator.locator("option").all()
                        for option in options:
                            text = (await option.inner_text()).strip()
                            if field.value.casefold() in text.casefold():
                                value = await option.get_attribute("value")
                                if value:
                                    await locator.select_option(value=value)
                                break
            elif field.field_type in ("radio", "checkbox", "choice"):
                option = dialog.get_by_label(field.value, exact=False)
                if await option.count() == 0:
                    option = dialog.get_by_text(field.value, exact=True)
                if await option.count() > 0:
                    await option.first.check()
            else:
                if context.settings.apply_human_typing and len(field.value) <= 240:
                    await locator.click()
                    await locator.press_sequentially(
                        field.value,
                        delay=random.randint(18, 70),
                    )
                else:
                    await locator.fill(field.value)
        except Exception as exc:
            logger.debug("No se pudo completar el campo %s: %s", field.label, exc)
            if field.required:
                field.status = "pending"


async def _on_review(page: Any, dialog: Any) -> bool:
    """Solo cuenta como revisión en el último paso del flujo."""
    progress = dialog.get_by_text(re.compile(r"\d+\s*/\s*\d+"))
    try:
        for index in range(min(await progress.count(), 5)):
            item = progress.nth(index)
            if not await item.is_visible():
                continue
            text = await item.inner_text()
            match = re.search(r"(\d+)\s*/\s*(\d+)", text)
            if match:
                return int(match.group(1)) >= int(match.group(2))
    except Exception:
        pass

    submit_names = re.compile(
        r"enviar solicitud|enviar postulación|submit application|submit your application",
        re.IGNORECASE,
    )
    try:
        locator = dialog.get_by_role("button", name=submit_names)
        for index in range(min(await locator.count(), 3)):
            if await locator.nth(index).is_visible():
                return True
    except Exception:
        pass

    heading = dialog.get_by_text(
        re.compile(
            r"review your application|revisar tu solicitud|tu solicitud está lista",
            re.IGNORECASE,
        )
    )
    try:
        for index in range(min(await heading.count(), 3)):
            if await heading.nth(index).is_visible():
                return True
    except Exception:
        pass
    return False


async def _visible_errors(page: Any) -> list[str]:
    errors: list[str] = []
    for selector in ('[role="alert"]:visible', ".artdeco-inline-feedback--error:visible"):
        locator = page.locator(selector)
        try:
            count = await locator.count()
        except Exception:
            continue
        for index in range(min(count, 3)):
            text = (await locator.nth(index).inner_text()).strip()
            if text and any(marker in text.casefold() for marker in ERROR_MARKERS):
                errors.append(text[:300])
    return errors


async def _click_next(page: Any, dialog: Any) -> bool:
    before = await dialog.inner_text()
    candidates = [
        dialog.get_by_role("button", name=NEXT_LABELS),
        page.get_by_role("button", name=NEXT_LABELS),
    ]
    for locator in candidates:
        try:
            if await locator.count() > 0:
                await locator.first.click()
                for _ in range(10):
                    await asyncio.sleep(0.5)
                    after = await dialog.inner_text()
                    if after != before:
                        return True
                return False
        except Exception:
            continue
    return False


async def _finish_with_screenshot(
    page: Any,
    context: ApplyContext,
    fields: list[FormField],
    status: str,
    message: str,
    browser_context: Any,
    playwright: Any,
    *,
    keep_open: bool = False,
) -> PrepareResult:
    screenshot = await _screenshot(page, context.settings, context.application_id, "review")
    result = PrepareResult(
        status=status,
        fields=fields,
        message=message,
        screenshot=screenshot,
        review_url=page.url,
        browser_state={"url": page.url},
    )
    if not keep_open:
        _stop_live_preview(context.application_id)
        await _safe_close(browser_context)
        await _safe_stop(playwright)
    return result


async def _screenshot(page: Any, settings: Settings, application_id: str, suffix: str) -> str:
    path = settings.artifacts_dir / f"{application_id}-{suffix}.png"
    try:
        await page.screenshot(path=str(path), full_page=False)
        return str(path)
    except Exception:
        logger.debug("No se pudo guardar la captura", exc_info=True)
        return ""


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def _safe_close(context: Any) -> None:
    try:
        await context.close()
    except Exception:
        logger.debug("No se pudo cerrar el contexto", exc_info=True)


async def _safe_stop(playwright: Any) -> None:
    try:
        await playwright.stop()
    except Exception:
        logger.debug("No se pudo detener Playwright", exc_info=True)
