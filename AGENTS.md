# Indoor GNSS Simulator Instructions

## Scope
- Keep active work in this project. Read README.md and docs/PHYSICS.md before changing models.
- Use Python 3.10+ and NumPy. Keep tests runnable with standard-library unittest.

## Scientific integrity
- Label all generated data as synthetic. Separate path truth, statistical observations and receiver estimates.
- Do not claim real constellation geometry for synthetic orbits, or cold-start navigation for IQ without validated LNAV.
- Record resolved parameters, random seeds, execution commands, software versions, sources and limitations.

## Validation
- Run the physics, ephemeris and IQ tests when changing models. Preserve distance/phase/Doppler consistency.
- Never overwrite existing experiment directories. Save each new run in a separate directory.
- Do not upload research data or unpublished results without user authorization.

## Documentation
- Update the parameter guide and model limitations when behavior changes.
- Any change to this file must update adjacent AGENTS.zh-notes.md with aligned meaning.
- The adjacent Chinese notes also include this English original for bilingual reading.
