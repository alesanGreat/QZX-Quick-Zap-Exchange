# QZX test evidence policy

The test suite combines precise unit checks with real-system integration
evidence. Both are useful, but they prove different things. A green mocked test
must never be presented as proof that QZX, a dependency, or an operating-system
feature works on the runner.

## The decision rule

A mock is acceptable only when the assertion is about harmless,
deterministic, predictable QZX-owned logic that does not vary by platform.
Examples include:

- formatting a normalized result as human output or JSON;
- mapping a QZX-owned value to a stable status or message;
- selecting a branch with no external effects;
- verifying that validation or an approval barrier blocks a mutation;
- exercising error presentation after the real boundary is tested elsewhere.

A mock may isolate a destructive, billable, secret-bearing, or external action
so its surrounding control flow can be tested safely. That unit test proves
only the control flow. Supported behavior still needs a real test in an
isolated environment; if that is unavailable, the limitation must be reported
instead of inferred away.

## What mocks must never certify

Do not use mocks, monkeypatches, artificial fixtures, platform substitutions,
or silent skips as compatibility evidence for:

- operating-system name, version, architecture, kernel, or Python build;
- `psutil`, syscalls, permissions, ownership, signals, or process behavior;
- paths, case sensitivity, links, locks, filesystems, or encodings;
- shells, quoting, executable resolution, package managers, or native tools;
- sockets, ports, DNS, interfaces, routes, or network access;
- native extensions or libraries.

These responses can differ across operating systems. Compatibility evidence
must obtain them from the real target system. In particular, never patch
`platform.system()`, `os.name`, `sys.platform`, `uname`, or an equivalent value
in a new test. Place platform-neutral logic behind a normalized QZX-owned
boundary and unit-test that boundary instead of mocking raw OS responses.
Existing tests that substitute platform identity or raw OS responses are
migration debt, not precedent, and cannot count as platform coverage.

## Required real-system layer

Every platform listed as verified must also run tests without mocks that:

1. verify the real OS release, architecture, CPython version, and build type;
2. import and exercise the installed native dependencies;
3. invoke QZX's public interface against a real, safe, controlled resource;
4. assert the relevant observable result or side effect;
5. fail visibly when the integration is unavailable or broken.

`integration/test_real_system_dependencies.py` is the current minimum for
system integration. It exercises the installed `psutil`, runs public
`systemDoctor`, and asks public `inspectPort` to detect a real listening socket.
The explicitly named Unix workflows run this layer separately before the
remaining suite so the source of a failure is visible.

## Review questions

Before accepting a mocked test, answer:

1. Is the assertion deterministic and independent of the host platform?
2. Is the mock testing QZX-owned logic rather than pretending an integration
   succeeded?
3. Could a real regression in permissions, native code, filesystem, process,
   shell, or networking remain hidden?
4. If the boundary is supported, where is its real-system test?
5. Would the compatibility claim remain honest if the mock were removed?

If questions 1, 2, or 5 cannot be answered yes, or question 3 can be answered
yes, the mock is in the wrong layer.

## Fixtures

Fixtures under this directory are test-only inputs and must not be referenced
by production code. They may represent deterministic content such as sample
source files or language text. They must not impersonate a platform-dependent
result and then be used as evidence that the real platform works.
