"""OpenAI Browser OAuth 테스트 스크립트."""

import asyncio

from ultimate_debate.auth.providers.openai_provider import OpenAIProvider
from ultimate_debate.auth.storage.token_store import TokenStore


async def main():
    """메인 테스트 함수."""
    print("OpenAI Browser OAuth 테스트 시작")
    print("=" * 60)

    provider = OpenAIProvider()
    store = TokenStore()

    try:
        # 기존 토큰 확인
        existing_token = await store.load("openai")
        if existing_token and not existing_token.is_expired():
            print(f"[OK] 기존 토큰 발견: {existing_token.access_token[:20]}...")
            print(f"[OK] 만료 시간: {existing_token.expires_at}")
            return

        # Browser OAuth 로그인
        print("\n[INFO] Browser OAuth 로그인 시작...")
        token = await provider.login(manual_mode=False)

        print(f"\n[OK] 로그인 성공!")
        print(f"[OK] Access Token: {token.access_token[:20]}...")
        print(f"[OK] Refresh Token: {token.refresh_token[:20] if token.refresh_token else None}...")
        print(f"[OK] Expires At: {token.expires_at}")

        # 토큰 저장
        await store.save(token)
        print(f"[OK] 토큰 저장 완료")

    except Exception as e:
        print(f"\n[ERROR] 인증 실패: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
