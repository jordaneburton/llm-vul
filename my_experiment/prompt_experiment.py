from typing import List, Dict


def build_baseline_prompt(code: str) -> str:
    return f"""Fix the security bug in the following Java code.
Return only the corrected Java code.

{code}
"""


def build_security_aware_prompt(code: str, cwe_id: str, cwe_description: str) -> str:
    return f"""The following Java code contains a security vulnerability.

CWE ID: {cwe_id}
Description: {cwe_description}

Fix the vulnerability securely and preserve the original functionality.
Return only the corrected Java code.

{code}
"""


def get_examples() -> List[Dict[str, str]]:
    return [
        {
            "title": "Incorrect string comparison",
            "cwe_id": "CWE-480",
            "description": "Use of incorrect operator that may cause insecure or incorrect comparison.",
            "code": """
public class Test {
    public boolean check(String role) {
        return role == "admin";
    }
}
""",
        },
        {
            "title": "Improper input validation",
            "cwe_id": "CWE-20",
            "description": "Improper input validation may allow unsafe or unexpected input.",
            "code": """
public class UserInput {
    public int parseAge(String age) {
        return Integer.parseInt(age);
    }
}
""",
        },
        {
            "title": "Hardcoded password",
            "cwe_id": "CWE-798",
            "description": "Use of hard-coded credentials can expose sensitive access information.",
            "code": """
public class LoginService {
    private static final String PASSWORD = "admin123";

    public boolean login(String inputPassword) {
        return PASSWORD.equals(inputPassword);
    }
}
""",
        },
    ]


def print_separator() -> None:
    print("=" * 70)


def run_experiment() -> None:
    examples = get_examples()

    for index, example in enumerate(examples, start=1):
        print_separator()
        print(f"Example {index}: {example['title']}")
        print(f"CWE: {example['cwe_id']}")
        print()

        baseline_prompt = build_baseline_prompt(example["code"])
        security_prompt = build_security_aware_prompt(
            example["code"],
            example["cwe_id"],
            example["description"],
        )

        print("=== Baseline Prompt ===")
        print(baseline_prompt)

        print("=== Security-Aware Prompt ===")
        print(security_prompt)
        print()


def main() -> None:
    run_experiment()


if __name__ == "__main__":
    main()