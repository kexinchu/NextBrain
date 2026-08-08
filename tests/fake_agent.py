"""Small subprocess agent used by CLI integration tests."""

import json
import os
import sys


sys.stdin.read()
role = os.environ["AUTORESEARCH_ROLE"]
digest = os.environ["AUTORESEARCH_REQUIREMENTS_DIGEST"]
decision = "satisfied" if role == "idea-challenger" else "continue"
story = "# CLI story\n\nThe topic-file workflow reached the challenger."
print(
    json.dumps(
        {
            "content": story,
            "story": story,
            "decision": decision,
            "summary": "fake agent completed",
            "alignment": {
                "requirements_digest": digest,
                "preserved_constraints": ["topic file"],
                "possible_drift": "none",
            },
            "files": {},
            "candidates": [{"id": "I-1"}],
            "challenge": "survives" if role == "idea-challenger" else "",
        }
    )
)
