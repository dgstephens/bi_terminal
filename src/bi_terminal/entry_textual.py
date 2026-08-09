"""Console-script entry point: `bi-terminal-textual`.

Not built yet — this is the very next piece of work (README "Sequencing",
step 2, the "tracer bullet": one screen round-tripping end-to-end through a
real TextualRenderer before the full ~15-screen port). renderers/textual/
currently has no renderer.py/app.py; only the package placeholder exists.
Raises a clear error rather than an ImportError so the four-entry-point
structure is provably real today even though this one specific renderer has
no implementation behind it yet.
"""


def main() -> None:
    raise NotImplementedError(
        "Textual renderer not yet built — see README Sequencing, step 2 (tracer bullet)"
    )


if __name__ == "__main__":
    main()
