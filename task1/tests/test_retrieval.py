import sqlite3
from contextlib import closing

def test_basic_keyword_scoring():
    terms = ["member", "profile"]
    text = "Member profile fields are configured in the dashboard."
    assert sum(text.lower().count(t) for t in set(terms)) == 2
