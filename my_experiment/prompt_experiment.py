def baseline_prompt(code):
    return f"Fix the bug in this Java code:\n{code}"


def security_prompt(code):
    return f"This code has a security vulnerability (CWE-89 SQL Injection). Fix it securely:\n{code}"


# Example test
java_code = """
public class Test {
    public boolean check(String role) {
        return role == "admin";
    }
}
"""

print("=== Baseline ===")
print(baseline_prompt(java_code))

print("\n=== Security Prompt ===")
print(security_prompt(java_code))