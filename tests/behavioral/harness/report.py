"""How a step ends: printed as it happens, kept for the artifact, and added up
into the run's exit code.

    PASS / FAIL   a verdict — FAIL fails the run
    WARN          something was off but the run can go on
    INFO          recorded, judged by nobody (see shell.note_kd_state)
"""

results: list[tuple[str, str, str]] = []


class ScenarioAborted(RuntimeError):
    """A step failed so badly that the rest of the scenario would prove nothing.

    Raised past the scenario body, never past the teardown: an abandoned run must
    still leave the screen as it found it.
    """


def reset() -> None:
    results.clear()


def report(step: str, status: str, detail: str = '') -> None:
    results.append((step, status, detail))
    print(f'[{status:4}] {step}' + (f' — {detail}' if detail else ''), flush=True)


def summary() -> int:
    failed = [r for r in results if r[1] == 'FAIL']
    steps = f'{len(results)} step' + ('' if len(results) == 1 else 's')
    print('\n' + ('FAILED' if failed else 'OK')
          + f' — {steps}, {len(failed)} failed')
    return 1 if failed else 0
