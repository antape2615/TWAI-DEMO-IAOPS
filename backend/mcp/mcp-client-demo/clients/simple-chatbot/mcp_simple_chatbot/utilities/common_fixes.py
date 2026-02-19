import re

COMMON_FIXES = {
    r"\bDynamoDB(Table)?\b": "Dynamodb",
    r"\bEventBridge\b": "Eventbridge",
    r"\bALB\b": "ELB",
    r"\bCognito(UserPools|Idp)?\b": "Cognito",
    r"\bSecurityGroup\b": "NetworkFirewall",
}

def apply_common_fixes(code: str) -> str:
    for pat, repl in COMMON_FIXES.items():
        code = re.sub(pat, repl, code)
    return code
