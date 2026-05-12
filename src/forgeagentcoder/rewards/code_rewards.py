from __future__ import annotations


def compute_patch_reward(
    *,
    pre_tests_passed: bool,
    patch_applied: bool,
    post_tests_passed: bool,
) -> float:
    """Simple executable-code reward for v0.

    Reward interpretation:
    - The best signal is post-patch tests passing.
    - Patch application matters.
    - Pre-tests passing means the task may not be a valid failing bugfix task.
    """
    reward = 0.0

    if patch_applied:
        reward += 0.25
    else:
        reward -= 1.0

    if post_tests_passed:
        reward += 1.0
    else:
        reward -= 0.5

    if pre_tests_passed:
        reward -= 0.25

    return round(reward, 6)
