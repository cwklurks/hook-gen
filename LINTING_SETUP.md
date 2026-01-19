# Linting, Formatting, and Type Checking Setup

This document describes the code quality tools configured for this repository.

## Python (Backend & hook-aid)

### Configuration File
- **`pyproject.toml`** at the repo root

### Tools Installed
- **ruff** - Fast Python linter and formatter
- **mypy** - Static type checker

### Ruff Configuration
- Line length: 100 characters
- Enabled rules:
  - `E` - pycodestyle errors
  - `F` - pyflakes
  - `I` - isort (import sorting)
  - `B` - flake8-bugbear (common bugs)

### Mypy Configuration
- Strict mode enabled (`strict = true`)
- Ignored missing imports for libraries without type stubs:
  - librosa, mido, pretty_midi, soundfile
  - fastapi, uvicorn, streamlit

### Running Python Linters

```bash
# Run ruff to check and auto-fix issues
ruff check --fix .

# Run ruff to just check (no fixes)
ruff check .

# Run mypy type checking
mypy backend hook-aid packages

# Format code with ruff
ruff format .
```

## TypeScript (Frontend)

### Configuration Files
- **`frontend/tsconfig.json`** - TypeScript configuration
- **`frontend/.prettierrc.json`** - Prettier configuration
- **`frontend/.prettierignore`** - Files to exclude from formatting
- **`frontend/eslint.config.mjs`** - ESLint configuration

### Tools Installed
- **prettier** - Code formatter
- **prettier-plugin-tailwindcss** - Tailwind CSS class sorting
- **eslint** - JavaScript/TypeScript linter (via Next.js)
- **typescript** - Type checker

### TypeScript Configuration
- Strict mode enabled (`"strict": true`)
- Additional strict options:
  - `noUnusedLocals: true`
  - `noUnusedParameters: true`
  - `noFallthroughCasesInSwitch: true`
  - `noImplicitReturns: true`
  - `noUncheckedIndexedAccess: true`
  - `forceConsistentCasingInFileNames: true`

### Prettier Configuration
- Semicolons: enabled
- Quotes: double quotes
- Tab width: 2 spaces
- Trailing commas: ES5 compatible
- Print width: 100 characters
- Tailwind CSS plugin enabled

### Running Frontend Linters

```bash
cd frontend

# Run ESLint and TypeScript type checking
npm run lint

# Run ESLint only
npm run lint:eslint

# Run TypeScript type checking only
npm run lint:types

# Format code with Prettier
npm run format

# Check if code is formatted (CI/CD)
npm run format:check
```

## Development Workflow

### Before Committing
1. **Python**: Run `ruff check --fix .` to auto-fix issues
2. **Frontend**: Run `npm run format` and `npm run lint` in the frontend directory
3. Fix any remaining errors reported by the tools

### In CI/CD
Consider adding these checks to your CI pipeline:
- Python: `ruff check . && mypy backend hook-aid packages`
- Frontend: `npm run format:check && npm run lint`

## Current Status

### Python
- Configuration: ✅ Complete
- Ruff: ✅ Working (some issues remain to be fixed)
- Mypy: ✅ Working (type annotations needed in many places)

### Frontend
- Configuration: ✅ Complete
- ESLint: ✅ Working (1 error, 2 warnings found)
- TypeScript: ✅ Working (7 type errors found - strict mode catching issues)
- Prettier: ✅ Configured

### Known Issues to Fix

**Frontend:**
- `src/app/page.tsx`: Unused variable `file`
- `src/app/page.tsx`: Type 'Note[] | undefined' not assignable to 'Note[]' (2 instances)
- `src/components/MusicBackground.tsx`: setState called synchronously in effect
- `src/components/MusicBackground.tsx`: Type mismatch in FloatingNote
- `src/components/SynthPlayer.tsx`: Missing dependency in useEffect
- `src/components/SynthPlayer.tsx`: Possibly undefined values (3 instances)

**Python:**
- Various long lines (>100 characters) - can be fixed gradually
- Module imports not at top of file (structural issue)
- Function call in default arguments (B008)
- Missing type annotations for strict mypy compliance

## Notes

- The strict settings will catch many issues that were previously silent
- Some existing code may need refactoring to pass all checks
- Focus on fixing new code first, then gradually improve existing code
- The user requested to ignore deep logical type errors initially and focus on configuration - this has been completed successfully




