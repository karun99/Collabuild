"""Collabuild Reach doctor — health check for all internet channels."""

import json

from .channels import get_channels


def check_all(config: dict | None = None) -> dict[str, dict]:
    """Check all channels and return a status dict.

    Each channel is checked independently. Errors in one channel
    never affect others.

    Returns:
        dict[name] = {
            "name": str,          # human-readable description
            "status": str,        # 'ok' | 'warn' | 'error' | 'off'
            "message": str,       # human-readable message
            "tier": int,          # 0=zero-config, 1=free login, 2=manual
            "backends": list[str],
            "active_backend": str | None,
        }
    """
    results = {}
    for ch in get_channels():
        try:
            result = ch.check(config)
            status = result.status
            message = result.message
        except Exception as e:
            status = "error"
            message = f"健康检查异常：{e}"

        results[ch.name] = {
            "name": ch.description,
            "status": status,
            "message": message,
            "tier": ch.tier,
            "backends": ch.backends,
            "active_backend": ch.active_backend,
        }
    return results


_STATUS_ICONS = {"ok": "✅", "warn": "⚠️", "error": "❌", "off": "❌"}


def format_report(results: dict[str, dict]) -> str:
    """Format channel results as a human-readable report."""
    lines = []
    lines.append("Collabuild Reach — 互联网渠道状态")
    lines.append("=" * 50)
    lines.append("")

    ok_count = sum(1 for r in results.values() if r["status"] == "ok")
    total = len(results)

    # Tier 0 — zero config
    tier0 = {k: r for k, r in results.items() if r["tier"] == 0}
    if tier0:
        lines.append("✅ 零配置渠道（装好即用）：")
        for _key, r in tier0.items():
            icon = _STATUS_ICONS.get(r["status"], "❓")
            active = f"（{r['active_backend']}）" if r.get("active_backend") else ""
            lines.append(f"  {icon} {r['name']}{active}")
            lines.append(f"     {r['message']}")
        lines.append("")

    # Tier 1 — free login
    tier1_active = {k: r for k, r in results.items() if r["tier"] == 1 and r["status"] == "ok"}
    tier1_inactive = {k: r for k, r in results.items() if r["tier"] == 1 and r["status"] != "ok"}
    if tier1_active:
        lines.append("🔓 可选渠道（已激活）：")
        for _key, r in tier1_active.items():
            lines.append(f"  ✅ {r['name']}（{r['active_backend']}）")
            lines.append(f"     {r['message']}")
        lines.append("")
    if tier1_inactive:
        lines.append("🔒 可选渠道（需配置）：")
        for _key, r in tier1_inactive.items():
            icon = _STATUS_ICONS.get(r["status"], "❓")
            lines.append(f"  {icon} {r['name']}")
            lines.append(f"     {r['message']}")
        lines.append("")

    # Tier 2 — manual setup
    tier2 = {k: r for k, r in results.items() if r["tier"] == 2}
    if tier2:
        lines.append("🛠️ 高级渠道（手动配置）：")
        for _key, r in tier2.items():
            icon = _STATUS_ICONS.get(r["status"], "❓")
            lines.append(f"  {icon} {r['name']} — {r['message']}")
        lines.append("")

    pct = round((ok_count / total) * 100) if total > 0 else 0
    lines.append(f"📊 {ok_count}/{total} 个渠道可用（{pct}%）")
    lines.append("")

    return "\n".join(lines)


def report_to_json(results: dict[str, dict]) -> str:
    """Format results as JSON."""
    return json.dumps(results, ensure_ascii=False, indent=2)
