"""Safe GitHub Issue entry points used by the desktop app."""

from urllib.parse import urlencode

from version import APP_VERSION


ISSUES_BASE_URL = "https://github.com/kimNarr/SynapCap/issues"
FEEDBACK_CHOOSER_URL = f"{ISSUES_BASE_URL}/new/choose"

_TEMPLATES = {
    "bug": ("bug_report.yml", "Bug"),
    "feature": ("feature_request.yml", "Feature"),
    "other": ("general_feedback.yml", "Feedback"),
}


def feedback_url(feedback_type: str) -> str:
    """Build an Issue Form URL without requesting a GitHub access token."""
    template = _TEMPLATES.get(feedback_type)
    if template is None:
        return FEEDBACK_CHOOSER_URL
    template_name, title_prefix = template
    query = urlencode(
        {
            "template": template_name,
            "title": f"[{title_prefix}] [v{APP_VERSION}] ",
        }
    )
    return f"{ISSUES_BASE_URL}/new?{query}"
