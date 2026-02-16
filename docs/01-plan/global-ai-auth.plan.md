# Global AI Auth Extraction Plan

**Status**: PLANNING
**Created**: 2026-02-16
**Owner**: -
**Complexity Score**: 7/10

---

## 배경

Ultimate Debate 프로젝트의 `auth/` 모듈은 현재 다음과 같은 특성을 가지고 있습니다:

- **범용 OAuth 라이브러리**: OpenAI, Google 등 다양한 AI 제공자의 인증을 처리
- **글로벌 토큰 저장 경로**: 이미 `~/.config/claude-code/ai-auth/` 등의 프로젝트 무관 경로 사용
- **단순 인증 로직**: 프로젝트 특화 로직 없음 (순수 OAuth 구현)

**문제점**: 현재 `from ultimate_debate.auth import ...` 형태로 패키징되어 있어, 다른 프로젝트(예: `automation_hub`, `vimeo_ott` 등)에서 재사용할 수 없습니다.

**기존 패턴**: `C:\claude\lib\` 디렉토리에 이미 `gmail/`, `slack/`, `google_docs/` 등의 공유 라이브러리가 존재하여 다른 프로젝트에서 import 가능합니다.

**목표**: `ultimate_debate.auth`를 `lib.ai_auth`로 추출하여, 모든 Claude 프로젝트에서 OAuth 인증을 공유 라이브러리로 사용할 수 있게 합니다.

---

## 구현 범위

### Task 1: auth 모듈을 C:\claude\lib\ai_auth\로 추출

**목표**: 현재 `src/ultimate_debate/auth/` 모듈을 `C:\claude\lib\ai_auth\`로 복사하고 독립적으로 동작하도록 준비합니다.

**구현 세부사항**:

1. **디렉토리 생성 및 파일 복사**
   ```
   C:\claude\lib\ai_auth\
   ├── flows/
   │   ├── __init__.py
   │   ├── base.py (신규: 기본 플로우 인터페이스)
   │   ├── browser_oauth.py
   │   ├── device_code.py
   │   └── codex_streaming.py (신규: OpenAI Codex SSE 스트리밍)
   ├── providers/
   │   ├── __init__.py
   │   ├── base.py
   │   ├── openai_provider.py
   │   ├── google_provider.py
   │   └── registry.py (신규: 제공자 레지스트리)
   ├── storage/
   │   ├── __init__.py
   │   └── token_store.py
   ├── exceptions.py
   ├── __init__.py (공개 API 정의)
   ├── __main__.py (CLI 진입점)
   └── tests/ (기본 테스트)
   ```

2. **내부 import 경로 정리**
   - `ultimate_debate.auth.*` → 제거
   - `lib.ai_auth.*` → 새로운 정규 경로
   - 상대 import → 절대 import로 변경 (lib.ai_auth.*)

3. **__init__.py 공개 API**
   ```python
   from lib.ai_auth.flows import BrowserOAuthFlow, DeviceCodeFlow
   from lib.ai_auth.providers import OpenAIProvider, GoogleProvider
   from lib.ai_auth.storage import TokenStore
   from lib.ai_auth.exceptions import (
       AuthenticationError,
       TokenExpiredError,
       TokenNotFoundError,
       OAuthError,
       RetryLimitExceededError,
   )

   __all__ = [
       "BrowserOAuthFlow",
       "DeviceCodeFlow",
       "OpenAIProvider",
       "GoogleProvider",
       "TokenStore",
       "AuthenticationError",
       "TokenExpiredError",
       "TokenNotFoundError",
       "OAuthError",
       "RetryLimitExceededError",
   ]
   ```

4. **requirements.txt 작성**
   - 의존성: `aiohttp`, `pydantic`, `keyring` 등
   - `C:\claude\lib\ai_auth\requirements.txt`

---

### Task 2: ultimate-debate 클라이언트 import 업데이트

**목표**: ultimate-debate 패키지 내 모든 auth import를 새로운 경로로 업데이트합니다.

**영향 파일**:

1. **src/ultimate_debate/clients/openai_client.py**
   ```python
   # Before
   from ultimate_debate.auth.flows import BrowserOAuthFlow
   from ultimate_debate.auth.providers import OpenAIProvider

   # After
   from lib.ai_auth.flows import BrowserOAuthFlow
   from lib.ai_auth.providers import OpenAIProvider
   ```

2. **src/ultimate_debate/clients/gemini_client.py**
   ```python
   # Before
   from ultimate_debate.auth.providers import GoogleProvider
   from ultimate_debate.auth.storage import TokenStore

   # After
   from lib.ai_auth.providers import GoogleProvider
   from lib.ai_auth.storage import TokenStore
   ```

3. **src/ultimate_debate/auth/__init__.py (하위호환성 shim)**
   ```python
   """
   Backward compatibility shim.
   All auth functionality has been moved to lib.ai_auth.

   This module re-exports for backward compatibility only.
   New code should import directly from lib.ai_auth.
   """

   import warnings

   warnings.warn(
       "ultimate_debate.auth is deprecated. "
       "Use lib.ai_auth instead.",
       DeprecationWarning,
       stacklevel=2
   )

   from lib.ai_auth import *  # noqa: F401, F403
   from lib.ai_auth.flows import BrowserOAuthFlow, DeviceCodeFlow
   from lib.ai_auth.providers import OpenAIProvider, GoogleProvider
   from lib.ai_auth.storage import TokenStore
   from lib.ai_auth.exceptions import *  # noqa: F401, F403

   __all__ = [
       "BrowserOAuthFlow",
       "DeviceCodeFlow",
       "OpenAIProvider",
       "GoogleProvider",
       "TokenStore",
   ]
   ```

**하위호환성 보장**: 기존 코드가 `from ultimate_debate.auth import ...` 형태로 작성되어도 deprecation warning과 함께 동작합니다.

---

### Task 3: CLI 진입점 추가

**목표**: `python -m lib.ai_auth` 명령으로 인증 관리를 수행할 수 있도록 합니다.

**구현**: `C:\claude\lib\ai_auth\__main__.py`

```python
#!/usr/bin/env python3
"""
CLI entry point for lib.ai_auth.

Usage:
    python -m lib.ai_auth login openai
    python -m lib.ai_auth login google
    python -m lib.ai_auth status
    python -m lib.ai_auth logout openai
"""

import asyncio
import argparse
import sys
from lib.ai_auth.providers import OpenAIProvider, GoogleProvider
from lib.ai_auth.storage import TokenStore


async def login_openai():
    """Interactive login for OpenAI."""
    provider = OpenAIProvider()
    token = await provider.authenticate()
    print(f"✓ OpenAI login successful")
    print(f"  Token expires at: {token.expires_at}")


async def login_google():
    """Interactive login for Google."""
    provider = GoogleProvider()
    token = await provider.authenticate()
    print(f"✓ Google login successful")
    print(f"  Token expires at: {token.expires_at}")


def status():
    """Check authentication status for all providers."""
    store = TokenStore()

    providers = ["openai", "google"]
    for provider_name in providers:
        has_token = store.has_valid_token(provider_name)
        status_str = "✓ Authenticated" if has_token else "✗ Not authenticated"
        print(f"{provider_name}: {status_str}")


def logout(provider_name: str):
    """Logout from a specific provider."""
    store = TokenStore()
    store.delete(provider_name)
    print(f"✓ Logged out from {provider_name}")


def main():
    parser = argparse.ArgumentParser(
        description="AI Auth CLI for managing OAuth tokens",
        prog="python -m lib.ai_auth"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Login subcommand
    login_parser = subparsers.add_parser("login", help="Login to an AI provider")
    login_parser.add_argument(
        "provider",
        choices=["openai", "google"],
        help="AI provider to login"
    )

    # Status subcommand
    subparsers.add_parser("status", help="Check authentication status")

    # Logout subcommand
    logout_parser = subparsers.add_parser("logout", help="Logout from a provider")
    logout_parser.add_argument(
        "provider",
        choices=["openai", "google"],
        help="Provider to logout"
    )

    args = parser.parse_args()

    if args.command == "login":
        if args.provider == "openai":
            asyncio.run(login_openai())
        elif args.provider == "google":
            asyncio.run(login_google())
    elif args.command == "status":
        status()
    elif args.command == "logout":
        logout(args.provider)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
```

**지원 명령**:
- `python -m lib.ai_auth login openai` - OpenAI 로그인
- `python -m lib.ai_auth login google` - Google 로그인
- `python -m lib.ai_auth status` - 인증 상태 확인
- `python -m lib.ai_auth logout <provider>` - 로그아웃

---

### Task 4: 테스트

**목표**: 추출된 모듈이 독립적으로 동작하고, 기존 ultimate-debate 테스트가 회귀되지 않도록 확인합니다.

**구현 세부사항**:

1. **lib.ai_auth 기본 테스트**
   - `C:\claude\lib\ai_auth\tests\test_imports.py`: import 경로 검증
   - `C:\claude\lib\ai_auth\tests\test_token_store.py`: TokenStore 기능
   - `C:\claude\lib\ai_auth\tests\test_providers.py`: Provider 인터페이스
   - `C:\claude\lib\ai_auth\tests\test_cli.py`: CLI 기본 동작

2. **ultimate-debate 회귀 테스트**
   ```bash
   # 기존 테스트 실행
   pytest C:\claude\ultimate-debate\tests\test_engine.py -v
   pytest C:\claude\ultimate-debate\tests\test_auth\test_providers.py -v
   pytest C:\claude\ultimate-debate\tests\test_auth\test_token_store.py -v
   ```

3. **import 호환성 검증**
   ```python
   # 새로운 import 경로
   from lib.ai_auth import TokenStore, OpenAIProvider, GoogleProvider

   # 하위호환 import (deprecated warning)
   from ultimate_debate.auth import TokenStore, OpenAIProvider, GoogleProvider
   ```

**테스트 기준**:
- ✓ lib.ai_auth에서 모든 공개 API import 가능
- ✓ ultimate_debate.auth에서 하위호환 import 가능 (warning 포함)
- ✓ 기존 ultimate-debate 테스트 모두 통과
- ✓ CLI 명령 정상 동작

---

## 영향 분석

### 변경 파일 목록

| 파일 | 상태 | 변경 내용 |
|------|------|----------|
| `C:\claude\lib\ai_auth\` | **신규** | 새로운 공유 라이브러리 패키지 |
| `src/ultimate_debate/clients/openai_client.py` | **수정** | import 경로 변경 |
| `src/ultimate_debate/clients/gemini_client.py` | **수정** | import 경로 변경 |
| `src/ultimate_debate/auth/` | **수정** | re-export shim만 유지 |
| `src/ultimate_debate/` | **기타** | 모든 auth 관련 import 경로 확인 |

### 의존성 변화

**추가되는 의존성** (lib.ai_auth):
- `aiohttp>=3.9.0`
- `pydantic>=2.0.0`
- `keyring>=24.0.0`

**변경되는 의존성**: 없음 (기존 ultimate-debate 의존성에 이미 포함)

---

## 위험 요소 및 완화 전략

### 1. Import 경로 변경으로 기존 테스트 깨짐 위험

**위험도**: 중간
**원인**: `ultimate_debate.auth` → `lib.ai_auth` 변경

**완화 전략**:
- re-export shim으로 하위호환성 보장
- deprecation warning으로 단계적 마이그레이션
- 모든 테스트 실행 전 import 호환성 검증

### 2. sys.path에 C:\claude 없으면 import 실패 위험

**위험도**: 높음
**원인**: lib.ai_auth는 C:\claude 아래에만 존재

**완화 전략**:
- `setup.py` 또는 `pyproject.toml`에 `C:\claude`를 namespace package로 등록
- 테스트 실행 시 PYTHONPATH 설정:
  ```bash
  export PYTHONPATH="C:\claude:$PYTHONPATH"
  ```
- `.pth` 파일 설치:
  ```python
  # .pth 파일 content
  import sys; sys.path.insert(0, 'C:\\claude')
  ```

### 3. 순환 의존성 위험

**위험도**: 낮음
**현황**: lib.ai_auth는 ultimate-debate에 의존하지 않음 (독립적)

**검증**:
```bash
python -c "from lib.ai_auth import TokenStore; print('OK')"
python -c "from ultimate_debate.clients import OpenAIClient; print('OK')"
```

### 4. 다른 프로젝트의 기존 auth 로직과 충돌

**위험도**: 낮음
**현황**: `automation_hub`, `vimeo_ott` 등에서 아직 auth 구현이 없거나 분산됨

**검증**: 기존 프로젝트에서 `from lib.ai_auth` import 테스트

---

## 예상 일정 및 작업량

| Task | 소요 시간 | 복잡도 | 의존성 |
|------|----------|--------|--------|
| Task 1: 모듈 추출 | 1-2시간 | 중간 | - |
| Task 2: Import 업데이트 | 30-45분 | 낮음 | Task 1 |
| Task 3: CLI 구현 | 30-45분 | 낮음 | Task 1 |
| Task 4: 테스트 | 1-2시간 | 중간 | Task 1-3 |
| **총합** | **3-5시간** | **7/10** | - |

---

## 사용 예시 (완료 후)

### 어떤 프로젝트에서든 OAuth 사용 가능

```python
# 1. 의존성 설치
# pip install C:\claude\lib\ai_auth

# 2. 코드에서 import
from lib.ai_auth import TokenStore, OpenAIProvider, GoogleProvider

# 3. OpenAI 토큰 확인
store = TokenStore()
if store.has_valid_token("openai"):
    token = store.load_sync("openai")
    # GPT API 호출에 token.access_token 사용
else:
    print("OpenAI not authenticated")

# 4. Google 토큰 확인
if store.has_valid_token("google"):
    token = store.load_sync("google")
    # Gemini API 호출에 token.access_token 사용
else:
    print("Google not authenticated")
```

### CLI로 인증 관리

```bash
# OpenAI 로그인 (브라우저 자동 열림)
python -m lib.ai_auth login openai

# Google 로그인
python -m lib.ai_auth login google

# 인증 상태 확인
python -m lib.ai_auth status

# OpenAI 로그아웃
python -m lib.ai_auth logout openai
```

### 기존 코드 마이그레이션 (단계별)

```python
# Phase 1: 현재 (작동하지만 deprecated warning)
from ultimate_debate.auth import TokenStore
# DeprecationWarning: ultimate_debate.auth is deprecated. Use lib.ai_auth instead.

# Phase 2: 권장 (새로운 코드)
from lib.ai_auth import TokenStore

# Phase 3: 향후 (ultimate_debate.auth 제거)
# from ultimate_debate.auth import TokenStore  # ImportError
```

---

## 성공 기준

| 기준 | 검증 방법 |
|------|----------|
| ✓ lib.ai_auth 독립 동작 | `python -c "from lib.ai_auth import *"` 성공 |
| ✓ 하위호환성 유지 | `from ultimate_debate.auth import *` 작동 + warning |
| ✓ CLI 동작 | `python -m lib.ai_auth status` 정상 출력 |
| ✓ 테스트 통과 | `pytest C:\claude\ultimate-debate\tests\test_auth\ -v` 100% pass |
| ✓ 다른 프로젝트 import 가능 | `from lib.ai_auth import TokenStore` (automation_hub 등) |

---

## 참고 문서

- Ultimate Debate CLAUDE.md: `C:\claude\ultimate-debate\CLAUDE.md`
- 기존 인증 아키텍처: `src/ultimate_debate/auth/`
- 공유 라이브러리 패턴: `C:\claude\lib\gmail\`, `C:\claude\lib\slack\`

---

## 다음 단계

1. 이 계획 문서 검토 및 승인
2. Task 1-4 순차 실행
3. 완료 후 다른 프로젝트(automation_hub, vimeo_ott)에서 lib.ai_auth 적용 검토
