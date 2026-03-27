---
name: llm-provider-testing
description: 'Structured workflow for testing and validating LLM provider integrations in AICA. Use when: testing new provider, validating streaming, debugging provider issues, ensuring retry logic works, verifying authentication.'
argument-hint: 'Describe the provider to test (e.g., "OpenRouter provider", "Anthropic streaming")'
---

# LLM Provider Testing Workflow

Comprehensive testing workflow for validating LLM provider integrations in AICA.

## When to Use

- Testing a new LLM provider implementation
- Validating sync/async/streaming capabilities
- Debugging provider connection or authentication issues
- Ensuring retry logic and error handling work correctly
- Verifying provider complies with `BaseLLMProvider` interface

## Prerequisites

- Provider implementation exists in `aica/core/llm/{provider}.py`
- Provider registered in `aica/core/llm/factory.py`
- API credentials available (if required)
- Understanding of the provider's authentication method

## Testing Workflow

### 1. Unit Tests - Core Methods

**Location:** `tests/test_{provider}_provider.py`

**Test all four required methods:**

```python
"""Tests for {Provider}Provider."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from unittest.mock import Mock, patch

import pytest

from aica.core.llm.{provider} import {Provider}Provider
from aica.core.llm.exceptions import LLMConnectionError, LLMAuthError


class Test{Provider}Provider:
    """Test suite for {Provider}Provider."""

    def test_generate_returns_string(self) -> None:
        """Test synchronous generate() returns complete string."""
        provider = {Provider}Provider(
            model="test-model",
            api_key="test-key",
            base_url="https://api.example.com"
        )

        with patch("httpx.Client.post") as mock_post:
            mock_post.return_value.json.return_value = {
                "choices": [{"message": {"content": "Hello world"}}]
            }

            result = provider.generate("Test prompt")

            assert isinstance(result, str)
            assert result == "Hello world"

    def test_stream_yields_tokens(self) -> None:
        """Test synchronous stream() yields token strings."""
        provider = {Provider}Provider(
            model="test-model",
            api_key="test-key",
            base_url="https://api.example.com"
        )

        with patch("httpx.Client.stream") as mock_stream:
            mock_stream.return_value.__enter__.return_value.iter_lines.return_value = [
                'data: {"choices":[{"delta":{"content":"Hello"}}]}',
                'data: {"choices":[{"delta":{"content":" world"}}]}'
            ]

            result = provider.stream("Test prompt")

            assert isinstance(result, Iterator)
            tokens = list(result)
            assert tokens == ["Hello", " world"]

    @pytest.mark.asyncio
    async def test_async_generate_returns_string(self) -> None:
        """Test async generate() returns complete string."""
        provider = {Provider}Provider(
            model="test-model",
            api_key="test-key",
            base_url="https://api.example.com"
        )

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value.json.return_value = {
                "choices": [{"message": {"content": "Hello async"}}]
            }

            result = await provider.async_generate("Test prompt")

            assert isinstance(result, str)
            assert result == "Hello async"

    @pytest.mark.asyncio
    async def test_async_stream_yields_tokens(self) -> None:
        """Test async stream() yields token strings."""
        provider = {Provider}Provider(
            model="test-model",
            api_key="test-key",
            base_url="https://api.example.com"
        )

        async def mock_iter_lines():
            yield 'data: {"choices":[{"delta":{"content":"Async"}}]}'
            yield 'data: {"choices":[{"delta":{"content":" tokens"}}]}'

        with patch("httpx.AsyncClient.stream") as mock_stream:
            mock_stream.return_value.__aenter__.return_value.aiter_lines.return_value = mock_iter_lines()

            result = provider.async_stream("Test prompt")

            assert isinstance(result, AsyncIterator)
            tokens = [token async for token in result]
            assert tokens == ["Async", " tokens"]
```

### 2. Error Handling Tests

**Test all exception scenarios:**

```python
def test_authentication_error(self) -> None:
    """Test provider raises LLMAuthError on 401/403."""
    provider = {Provider}Provider(
        model="test-model",
        api_key="invalid-key",
        base_url="https://api.example.com"
    )

    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value.status_code = 401
        mock_post.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized", request=Mock(), response=Mock(status_code=401)
        )

        with pytest.raises(LLMAuthError):
            provider.generate("Test")


def test_connection_error(self) -> None:
    """Test provider raises LLMConnectionError on network failure."""
    provider = {Provider}Provider(
        model="test-model",
        api_key="test-key",
        base_url="https://api.example.com"
    )

    with patch("httpx.Client.post") as mock_post:
        mock_post.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(LLMConnectionError):
            provider.generate("Test")


def test_timeout_error(self) -> None:
    """Test provider raises LLMTimeoutError on timeout."""
    provider = {Provider}Provider(
        model="test-model",
        api_key="test-key",
        base_url="https://api.example.com"
    )

    with patch("httpx.Client.post") as mock_post:
        mock_post.side_effect = httpx.TimeoutException("Request timeout")

        with pytest.raises(LLMTimeoutError):
            provider.generate("Test")
```

### 3. Retry Logic Tests

**Verify exponential backoff and retry behavior:**

```python
def test_retries_on_rate_limit(self) -> None:
    """Test provider retries on 429 rate limit."""
    provider = {Provider}Provider(
        model="test-model",
        api_key="test-key",
        base_url="https://api.example.com"
    )

    with patch("httpx.Client.post") as mock_post:
        # First two calls fail with 429, third succeeds
        mock_post.side_effect = [
            Mock(status_code=429, raise_for_status=Mock(side_effect=httpx.HTTPStatusError("429", request=Mock(), response=Mock(status_code=429)))),
            Mock(status_code=429, raise_for_status=Mock(side_effect=httpx.HTTPStatusError("429", request=Mock(), response=Mock(status_code=429)))),
            Mock(json=Mock(return_value={"choices": [{"message": {"content": "Success"}}]}))
        ]

        result = provider.generate("Test")

        assert result == "Success"
        assert mock_post.call_count == 3


def test_max_retries_exceeded(self) -> None:
    """Test provider fails after max retries exceeded."""
    provider = {Provider}Provider(
        model="test-model",
        api_key="test-key",
        base_url="https://api.example.com"
    )

    with patch("httpx.Client.post") as mock_post:
        mock_post.side_effect = httpx.HTTPStatusError(
            "429 Rate Limited", request=Mock(), response=Mock(status_code=429)
        )

        with pytest.raises(LLMConnectionError):
            provider.generate("Test")
```

### 4. Integration Tests

**Test with actual API (optional, requires credentials):**

```python
@pytest.mark.integration
@pytest.mark.skipif(not os.getenv("{PROVIDER}_API_KEY"), reason="API key not set")
def test_real_generate(self) -> None:
    """Test actual API call (requires valid credentials)."""
    provider = {Provider}Provider(
        model=os.getenv("{PROVIDER}_MODEL", "default-model"),
        api_key=os.getenv("{PROVIDER}_API_KEY"),
        base_url=os.getenv("{PROVIDER}_BASE_URL")
    )

    result = provider.generate("Say hello in one word")

    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("{PROVIDER}_API_KEY"), reason="API key not set")
async def test_real_async_stream(self) -> None:
    """Test actual streaming API call."""
    provider = {Provider}Provider(
        model=os.getenv("{PROVIDER}_MODEL", "default-model"),
        api_key=os.getenv("{PROVIDER}_API_KEY"),
        base_url=os.getenv("{PROVIDER}_BASE_URL")
    )

    tokens = []
    async for token in provider.async_stream("Count to 3"):
        tokens.append(token)

    assert len(tokens) > 0
    full_response = "".join(tokens)
    assert len(full_response) > 0
```

### 5. Factory Registration Tests

**Test provider is properly registered:**

```python
from aica.core.llm.factory import create_llm_provider


def test_factory_creates_provider() -> None:
    """Test factory can create provider instance."""
    provider = create_llm_provider(
        provider_name="{provider}",
        model="test-model",
        api_key="test-key"
    )

    assert isinstance(provider, {Provider}Provider)
    assert provider.model == "test-model"


def test_factory_validates_required_params() -> None:
    """Test factory raises error for missing required params."""
    with pytest.raises(ValueError, match="api_key"):
        create_llm_provider(
            provider_name="{provider}",
            model="test-model"
            # Missing api_key
        )
```

### 6. Manual Testing Checklist

**Interactive testing with real provider:**

#### Setup Environment

```bash
# Set credentials
export {PROVIDER}_API_KEY="your-api-key"
export {PROVIDER}_BASE_URL="https://api.example.com"
export {PROVIDER}_MODEL="model-name"
```

#### Test Sync Generation

```python
from aica.core.llm.factory import create_llm_provider

provider = create_llm_provider("{provider}", model="test-model")
result = provider.generate("Hello, how are you?")
print(result)
```

#### Test Sync Streaming

```python
for token in provider.stream("Count from 1 to 5"):
    print(token, end="", flush=True)
print()
```

#### Test Async Generation

```python
import asyncio

async def test_async():
    result = await provider.async_generate("Tell me a joke")
    print(result)

asyncio.run(test_async())
```

#### Test Async Streaming

```python
async def test_async_stream():
    async for token in provider.async_stream("Write a haiku"):
        print(token, end="", flush=True)
    print()

asyncio.run(test_async_stream())
```

### 7. Performance Testing

**Test response times and throughput:**

```python
import time


def test_generate_performance() -> None:
    """Test generate() completes in reasonable time."""
    provider = {Provider}Provider(
        model="test-model",
        api_key="test-key",
        base_url="https://api.example.com"
    )

    start = time.time()
    result = provider.generate("Quick test")
    duration = time.time() - start

    assert duration < 10.0, f"Generate took {duration}s, expected <10s"


def test_stream_first_token_latency() -> None:
    """Test streaming returns first token quickly."""
    provider = {Provider}Provider(
        model="test-model",
        api_key="test-key",
        base_url="https://api.example.com"
    )

    start = time.time()
    stream = provider.stream("Quick test")
    first_token = next(stream)
    first_token_time = time.time() - start

    assert first_token_time < 5.0, f"First token took {first_token_time}s"
    assert isinstance(first_token, str)
```

### 8. Security Testing

**Verify secrets are not logged:**

```python
def test_api_key_not_in_logs(caplog) -> None:
    """Test API key is not exposed in logs."""
    provider = {Provider}Provider(
        model="test-model",
        api_key="secret-key-12345",
        base_url="https://api.example.com"
    )

    with patch("httpx.Client.post") as mock_post:
        mock_post.side_effect = Exception("Test error")

        try:
            provider.generate("Test")
        except Exception:
            pass

    # Check logs don't contain API key
    for record in caplog.records:
        assert "secret-key-12345" not in record.message


def test_api_key_masked_in_repr() -> None:
    """Test API key is masked in object representation."""
    provider = {Provider}Provider(
        model="test-model",
        api_key="secret-key-12345",
        base_url="https://api.example.com"
    )

    repr_str = repr(provider)
    assert "secret-key-12345" not in repr_str
    assert "***" in repr_str or "[REDACTED]" in repr_str
```

## Quality Checklist

Before considering provider testing complete:

- [ ] All four core methods tested (generate, stream, async_generate, async_stream)
- [ ] Authentication error handling tested
- [ ] Connection error handling tested
- [ ] Timeout error handling tested
- [ ] Retry logic tested with rate limits
- [ ] Max retries exceeded tested
- [ ] Factory registration tested
- [ ] Manual interactive testing completed
- [ ] Performance benchmarks acceptable
- [ ] API keys not exposed in logs
- [ ] Test coverage >80%
- [ ] Integration tests pass (if applicable)
- [ ] All tests pass: `pytest tests/test_{provider}_provider.py -v`

## Common Testing Pitfalls

❌ **Not mocking HTTP calls in unit tests:**

```python
def test_generate():
    provider = MyProvider(...)
    result = provider.generate("test")  # Makes real API call!
```

✅ **Proper mocking:**

```python
def test_generate():
    provider = MyProvider(...)
    with patch("httpx.Client.post") as mock:
        mock.return_value.json.return_value = {"response": "test"}
        result = provider.generate("test")
```

❌ **Not testing async iterators properly:**

```python
async def test_stream():
    result = await provider.async_stream("test")  # Wrong!
```

✅ **Consuming async iterator:**

```python
async def test_stream():
    tokens = [token async for token in provider.async_stream("test")]
    assert len(tokens) > 0
```

❌ **Exposing API keys in tests:**

```python
provider = MyProvider(api_key="sk-real-key-here")  # Never commit real keys!
```

✅ **Using environment variables or mocks:**

```python
provider = MyProvider(api_key=os.getenv("TEST_API_KEY", "mock-key"))
```

## Running Tests

```bash
# Unit tests only (fast, no API calls)
pytest tests/test_{provider}_provider.py -v -m "not integration"

# Integration tests (requires API key)
export {PROVIDER}_API_KEY="your-key"
pytest tests/test_{provider}_provider.py -v -m integration

# With coverage
pytest tests/test_{provider}_provider.py --cov=aica.core.llm.{provider} --cov-report=term-missing

# All tests
pytest tests/ -v
```

## Related Resources

- [BaseLLMProvider Interface](../../aica/core/llm/base.py)
- [Existing Providers](../../aica/core/llm/) - Reference implementations
- [Factory Pattern](../../aica/core/llm/factory.py)
- [LLM Exceptions](../../aica/core/llm/exceptions.py)

## Example Invocation

```
/llm-provider-testing Validate the OpenRouter streaming implementation
```
