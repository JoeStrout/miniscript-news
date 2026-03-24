"""Shared LLM calling interface with usage tracking."""

# Running totals for the session
_total_input_tokens = 0
_total_output_tokens = 0


def call_llm(prompt, config):
    """Send the prompt to the configured LLM and return the response text."""
    global _total_input_tokens, _total_output_tokens

    llm_config = config.get("llm", {})
    provider = llm_config.get("provider", "anthropic")

    if provider == "anthropic":
        import anthropic
        api_key = config.get("anthropic_api_key")
        client = anthropic.Anthropic(**{"api_key": api_key} if api_key else {})
        model = llm_config.get("model", "claude-sonnet-4-20250514")
        message = client.messages.create(
            model=model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        _total_input_tokens += message.usage.input_tokens
        _total_output_tokens += message.usage.output_tokens
        return message.content[0].text

    elif provider == "openai":
        import openai
        api_key = config.get("openai_api_key")
        client = openai.OpenAI(**{"api_key": api_key} if api_key else {})
        model = llm_config.get("model", "gpt-4o")
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        if response.usage:
            _total_input_tokens += response.usage.prompt_tokens
            _total_output_tokens += response.usage.completion_tokens
        return response.choices[0].message.content

    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


def print_usage_report(config):
    """Print a summary of LLM token usage and estimated cost."""
    llm_config = config.get("llm", {})
    input_price = llm_config.get("input_price_per_m", 0)
    output_price = llm_config.get("output_price_per_m", 0)

    input_cost = _total_input_tokens * input_price / 1_000_000
    output_cost = _total_output_tokens * output_price / 1_000_000
    total_cost = input_cost + output_cost

    print(f"\nLLM usage: {_total_input_tokens:,} input + {_total_output_tokens:,} output tokens")
    if input_price or output_price:
        print(f"Estimated cost: ${total_cost:.4f} (${input_cost:.4f} input + ${output_cost:.4f} output)")
