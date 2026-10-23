"""Catálogo canónico de skills y sinónimos usados por CV y ofertas."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SkillDefinition:
    slug: str
    name: str
    category: str
    aliases: tuple[str, ...] = ()


SKILLS: tuple[SkillDefinition, ...] = (
    SkillDefinition("python", "Python", "backend", ("python3",)),
    SkillDefinition("javascript", "JavaScript", "frontend", ("js", "ecmascript")),
    SkillDefinition("typescript", "TypeScript", "frontend", ("ts",)),
    SkillDefinition("php", "PHP", "backend"),
    SkillDefinition("nodejs", "Node.js", "backend", ("node", "node js")),
    SkillDefinition("react", "React", "frontend", ("reactjs", "react.js")),
    SkillDefinition("nextjs", "Next.js", "frontend", ("next", "next js")),
    SkillDefinition("astro", "Astro", "frontend"),
    SkillDefinition("flutter", "Flutter", "mobile"),
    SkillDefinition("expo", "Expo", "mobile"),
    SkillDefinition("html", "HTML", "frontend", ("html5",)),
    SkillDefinition("css", "CSS", "frontend", ("css3",)),
    SkillDefinition("wordpress", "WordPress", "cms"),
    SkillDefinition("sql", "SQL", "data"),
    SkillDefinition("postgresql", "PostgreSQL", "data", ("postgres", "postgre")),
    SkillDefinition("mysql", "MySQL", "data"),
    SkillDefinition("sqlite", "SQLite", "data"),
    SkillDefinition("supabase", "Supabase", "data"),
    SkillDefinition("pocketbase", "PocketBase", "data"),
    SkillDefinition("firebase", "Firebase", "data"),
    SkillDefinition("redis", "Redis", "data"),
    SkillDefinition("docker", "Docker", "devops"),
    SkillDefinition("git", "Git", "devops"),
    SkillDefinition("github", "GitHub", "devops"),
    SkillDefinition("github-actions", "GitHub Actions", "devops", ("actions",)),
    SkillDefinition("ci-cd", "CI/CD", "devops", ("cicd", "integración continua")),
    SkillDefinition("linux", "Linux", "devops"),
    SkillDefinition("vps", "VPS", "devops"),
    SkillDefinition("cloudflare", "Cloudflare", "cloud"),
    SkillDefinition("vercel", "Vercel", "cloud"),
    SkillDefinition("aws", "AWS", "cloud", ("amazon web services",)),
    SkillDefinition("serverless", "Serverless", "cloud"),
    SkillDefinition("rest", "REST APIs", "backend", ("api rest", "rest api", "apis")),
    SkillDefinition("webhooks", "Webhooks", "backend"),
    SkillDefinition(
        "mcp", "Model Context Protocol", "ai", ("mcp server", "model context protocol")
    ),
    SkillDefinition("llm", "LLM", "ai", ("large language model", "modelos de lenguaje")),
    SkillDefinition(
        "prompt-engineering",
        "Prompt Engineering",
        "ai",
        ("prompt engineer", "ingeniería de prompts"),
    ),
    SkillDefinition("ai-agents", "Agentes de IA", "ai", ("ai agents", "agentes")),
    SkillDefinition("claude-code", "Claude Code", "ai"),
    SkillDefinition("opencode", "OpenCode", "ai"),
    SkillDefinition("gemini-cli", "Gemini CLI", "ai"),
    SkillDefinition("codex", "Codex", "ai"),
    SkillDefinition("antigravity", "Antigravity", "ai"),
    SkillDefinition("google-ads", "Google Ads", "marketing", ("adwords", "google adwords")),
    SkillDefinition("google-ads-search", "Google Ads Search", "marketing", ("search ads", "sem")),
    SkillDefinition("sem", "SEM", "marketing", ("search engine marketing",)),
    SkillDefinition("seo", "SEO", "marketing", ("posicionamiento orgánico",)),
    SkillDefinition("seo-tecnico", "SEO técnico", "marketing", ("technical seo",)),
    SkillDefinition("ga4", "Google Analytics 4", "analytics", ("google analytics", "analytics")),
    SkillDefinition("gtm", "Google Tag Manager", "analytics", ("tag manager",)),
    SkillDefinition("hotjar", "Hotjar", "analytics"),
    SkillDefinition("clarity", "Microsoft Clarity", "analytics", ("ms clarity",)),
    SkillDefinition("adsense", "AdSense", "marketing"),
    SkillDefinition("meta-ads", "Meta Ads", "marketing", ("facebook ads", "meta ads")),
    SkillDefinition("landing-pages", "Landing pages", "marketing", ("landing page",)),
    SkillDefinition("cro", "CRO", "marketing", ("conversion rate optimization", "conversión")),
    SkillDefinition("email-marketing", "Email marketing", "marketing"),
    SkillDefinition("keyword-research", "Keyword research", "marketing", ("keyword planner",)),
    SkillDefinition("core-web-vitals", "Core Web Vitals", "marketing", ("pagespeed",)),
    SkillDefinition("search-console", "Google Search Console", "marketing", ("search console",)),
    SkillDefinition("schema-markup", "Datos estructurados", "marketing", ("structured data",)),
    SkillDefinition("figma", "Figma", "design"),
    SkillDefinition("ux", "UX", "design", ("user experience", "lean ux")),
    SkillDefinition("copywriting", "Copywriting", "marketing", ("copy",)),
    SkillDefinition("scrum", "Scrum", "management"),
    SkillDefinition("jira", "Jira", "management"),
    SkillDefinition("solid", "SOLID", "engineering"),
    SkillDefinition("dry", "DRY", "engineering"),
    SkillDefinition("kiss", "KISS", "engineering"),
    SkillDefinition("yagni", "YAGNI", "engineering"),
    SkillDefinition("grasp", "GRASP", "engineering"),
    SkillDefinition("pola", "POLA", "engineering"),
    SkillDefinition("owasp", "OWASP", "security"),
    SkillDefinition(
        "multi-tenant", "Multi-tenancy", "architecture", ("multi tenant", "multitenant")
    ),
    SkillDefinition("rls", "Row Level Security", "security", ("row level security",)),
    SkillDefinition(
        "auth", "Autenticación y autorización", "security", ("authentication", "authorization")
    ),
    SkillDefinition("realtime", "Tiempo real", "backend", ("realtime", "websocket", "websockets")),
    SkillDefinition("geolocation", "Geolocalización", "product", ("geolocalización", "maps")),
    SkillDefinition("ecommerce", "Ecommerce", "product", ("e-commerce", "tienda online")),
    SkillDefinition("saas", "SaaS", "product"),
    SkillDefinition("marketplace", "Marketplace", "product"),
    SkillDefinition("analytics", "Analítica", "analytics", ("measurement", "medición")),
    SkillDefinition("visual-basic", "Visual Basic", "legacy", ("vb6", "visual basic 6")),
    SkillDefinition("java", "Java", "backend"),
    SkillDefinition("c", "C", "backend"),
    SkillDefinition("cpp", "C++", "backend", ("c plus plus",)),
)

SKILL_BY_SLUG = {skill.slug: skill for skill in SKILLS}

# Ordenados de más largo a más corto para que "Google Ads Search" gane a "Google Ads".
ALIAS_TO_SLUG: dict[str, str] = {}
for skill in SKILLS:
    ALIAS_TO_SLUG[skill.name.casefold()] = skill.slug
    ALIAS_TO_SLUG[skill.slug.casefold()] = skill.slug
    for alias in skill.aliases:
        ALIAS_TO_SLUG[alias.casefold()] = skill.slug

SORTED_ALIASES = sorted(ALIAS_TO_SLUG, key=len, reverse=True)


def canonical_slug(value: str) -> str | None:
    """Devuelve el slug canónico de una skill o alias, si existe."""
    return ALIAS_TO_SLUG.get(value.strip().casefold())


def _alias_pattern(alias: str) -> re.Pattern[str]:
    """Evita que "java" coincida dentro de "javascript" o "C" dentro de "CSS"."""
    return re.compile(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", re.IGNORECASE)


_PATTERNS = [(alias, _alias_pattern(alias)) for alias in SORTED_ALIASES]


def detect_skills(text: str) -> list[SkillDefinition]:
    """Detecta skills por alias, evitando duplicados y falsos positivos simples."""
    found: list[SkillDefinition] = []
    seen: set[str] = set()
    for alias, pattern in _PATTERNS:
        if len(alias) < 2:
            continue
        if pattern.search(text):
            slug = ALIAS_TO_SLUG[alias]
            if slug not in seen:
                seen.add(slug)
                found.append(SKILL_BY_SLUG[slug])
    return found
