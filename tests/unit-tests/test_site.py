"""
tests/unit-tests/test_site.py — Sanity checks for site deployment files.
"""
from pathlib import Path


def test_site_cname_exists():
    """site/CNAME must always exist and contain opensak.com.

    If this test fails, site/CNAME has been deleted or changed,
    and opensak.com will go down on the next deploy!
    """
    cname = Path("site/CNAME")
    assert cname.exists(), "site/CNAME is missing — opensak.com will go down on next deploy!"
    assert cname.read_text().strip() == "opensak.com", (
        f"site/CNAME contains wrong domain: {cname.read_text().strip()!r}"
    )
