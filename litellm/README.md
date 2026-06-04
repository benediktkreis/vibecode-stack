# Start everything

```
docker compose up -d
```

# Public access for Cursor (pick one)

`litellm` runs as a normal Docker service on port `4001`. Cursor needs a **public HTTPS** base URL — use **either** Tailscale Funnel **or** a Cloudflare quick tunnel, not both at once. You do not need to run Cloudflare if Funnel is already set up, and you do not need Funnel if you are using Cloudflare.

| Path | When to use |
|------|-------------|
| **Tailscale Funnel** (default) | Stable `https://litellm-proxy.tail-xxxxx.ts.net` URL; requires the `tailscale` service and a tailnet auth key |
| **Cloudflare quick tunnel** | Ephemeral `trycloudflare.com` URL; no Funnel approval; good for quick tests |

Set `LITELLM_BASE_URL` in `.env` to whichever public URL you chose. The sections below describe each option.

1. Create a **reusable** auth key: [Tailscale keys](https://login.tailscale.com/admin/settings/keys).
2. Add to `.env`:
   ```bash
   TS_AUTHKEY=tskey-auth-...
   TS_HOSTNAME=litellm-proxy
   LITELLM_BASE_URL=https://litellm-proxy.tail-xxxxx.ts.net
   ```
   Replace `tail-xxxxx` with your tailnet suffix (see [Machines](https://login.tailscale.com/admin/machines) after the first `docker compose up`).
3. Enable **MagicDNS**: [DNS settings](https://login.tailscale.com/admin/dns).
4. Start: `docker compose up -d`

## Tailscale Funnel for Cursor (recommended public path)

If you are not using the Cloudflare section below, use Funnel as your single public HTTPS URL.

Cursor rejects private provider URLs, including `127.0.0.1`, LAN IPs, and private Tailscale `100.x` addresses. Funnel exposes LiteLLM on the stable MagicDNS hostname:

```bash
docker exec litellm-tailscale tailscale funnel --bg --https=443 --yes http://litellm:4001
docker exec litellm-tailscale tailscale funnel status
```

On first use, Tailscale may print an approval URL. Open it, enable Funnel for this node, then rerun the `tailscale funnel` command.

Expected status:

```text
https://litellm-proxy.tail-xxxxx.ts.net
|-- / proxy http://litellm:4001
```

Use this URL in Cursor:

```text
Base URL: https://litellm-proxy.tail-xxxxx.ts.net
API key:  LITELLM_MASTER_KEY
```

Funnel is public internet exposure. LiteLLM's `LITELLM_MASTER_KEY` protects the API, so keep it strong.

## Cloudflare quick tunnel (alternative to Funnel)

Use this **instead of** Tailscale Funnel when you want a public URL without enabling Funnel on your tailnet node. Do not run Funnel and Cloudflare at the same time unless you intentionally want two public entry points; for normal use, pick one and set `LITELLM_BASE_URL` accordingly.

The quick-tunnel URL is ephemeral and can change after sleep, restart, or tunnel recreation.

Start the optional Cloudflare tunnel:

```bash
docker compose --profile cloudflare-quick up -d cloudflared-quick
```

Read the current `trycloudflare.com` URL:

```bash
docker compose logs cloudflared-quick | grep -o 'https://.*\.trycloudflare\.com' | tail -1
```

Use that printed URL in Cursor with `LITELLM_MASTER_KEY`.

To make the README helper functions use Cloudflare instead of Funnel, temporarily set `.env` to the printed URL:

```bash
LITELLM_BASE_URL=https://your-current-quick-tunnel.trycloudflare.com
```

Set it back to the Funnel URL when you want the stable Tailscale path again.

Stop the Cloudflare tunnel when you do not want it exposed:

```bash
docker compose --profile cloudflare-quick stop cloudflared-quick
```

The Cloudflare quick tunnel targets `http://litellm:4001`; it does not proxy through Tailscale.

## Tailnet-only access

On each **client device**, install the Tailscale app and sign in to the same tailnet (no Tailscale required on the Docker host beyond the container).

Enable a tailnet-only HTTP listener on port `4001`:

```bash
docker exec litellm-tailscale tailscale serve --bg --http=4001 http://litellm:4001
```

```bash
# From any device on the tailnet
curl "http://${TS_HOSTNAME}.tail-xxxxx.ts.net:4001/health/liveliness"
curl "http://${TS_HOSTNAME}.tail-xxxxx.ts.net:4001/v1/models" -H "Authorization: Bearer $LITELLM_MASTER_KEY"
```

Optional local access on the Docker host (port published by the `litellm` service):

```bash
curl http://127.0.0.1:4001/health/liveliness
```

If the `tailscale` container fails to start on Mac, keep `TS_USERSPACE=true` in `.env` (default). On Linux you can try `TS_USERSPACE=false` for kernel mode.

Use `${LITELLM_BASE_URL}` and `LITELLM_MASTER_KEY` from `.env` in Claude Code. The helper below routes `codex-*` models directly through LiteLLM's Claude-compatible endpoint, and routes all other models through Claude Code Router into LiteLLM's OpenAI-compatible chat endpoint. For OpenAI-compatible clients, use `${LITELLM_BASE_URL}` or `${LITELLM_BASE_URL}/v1` depending on what that client expects.

# CLIProxyAPI-backed Codex models

`Cursor/client -> (Tailscale Funnel **or** Cloudflare quick tunnel — one public path) -> LiteLLM -> CLIProxyAPI (Docker :8317)`

Tailnet-only clients can also use `http://litellm-proxy.tail-xxxxx.ts.net:4001`.

The compose stack:

- `tailscale` — tailnet identity and Funnel ingress
- `tailscale funnel` — public HTTPS URL for Cursor
- `cloudflared-quick` — optional ephemeral Cloudflare quick tunnel profile
- `litellm` — gateway on Docker port `4001`
- `cliproxyapi` — Codex OAuth-backed upstream access

Authenticate Codex OAuth against the running `cliproxyapi` container:

```bash
docker compose exec cliproxyapi /CLIProxyAPI/CLIProxyAPI --codex-login --no-browser
```


## Notes for CLIProxyAPI Gemini CLI + Antigravity
- I was not able to make the gemini cli via CLIProxyAPI work. And account gets banned for terms voilation for using antigravity via this.

I use the following functions in my bashrc

```
litellm_base_url() {
  if [ -n "${LITELLM_BASE_URL:-}" ]; then
    echo "${LITELLM_BASE_URL%/}"
    return 0
  fi
  echo "Set LITELLM_BASE_URL in $HOME/vibecode/litellm/.env (e.g. https://litellm-proxy.tail-xxxxx.ts.net)" >&2
  return 1
}

use_litellm_cursor() {
  local DB="$HOME/Library/Application Support/Cursor/User/globalStorage/state.vscdb"
  local JSON_KEY="src.vs.platform.reactivestorage.browser.reactiveStorageServiceImpl.persistentStorage.applicationUser"
  local LITTELM_KEY="..."
  local LITELLM_DIR="$HOME/vibecode/litellm"

  pkill -x Cursor || true
  sleep 1

  if [ "$1" = "reset" ]; then
    sqlite3 "$DB" "UPDATE ItemTable SET value = json_remove(value, '$.openAIBaseUrl') WHERE key = '$JSON_KEY';"
    sqlite3 "$DB" "UPDATE ItemTable SET value = '' WHERE key = 'cursorAuth/openAIKey';"
    echo "✅ Reset to native Cursor models"
  else
    if [ -f "$LITELLM_DIR/.env" ]; then
      set -a
      # shellcheck source=/dev/null
      source "$LITELLM_DIR/.env"
      set +a
    fi

    local LITTELM_URL
    LITTELM_URL=$(litellm_base_url)

    echo "🌐 Litellm proxy URL: $LITTELM_URL"

    sqlite3 "$DB" "UPDATE ItemTable SET value = json_set(value, '$.openAIBaseUrl', '$LITTELM_URL') WHERE key = '$JSON_KEY';"
    sqlite3 "$DB" "UPDATE ItemTable SET value = '$LITTELM_KEY' WHERE key = 'cursorAuth/openAIKey';"
    echo "✅ Switched to Litellm Proxy (base URL set to printed URL above)"
  fi
  open "cursor://command/workbench.action.reloadWindow"

}

use_litellm_claude() {
  if [ "${1:-}" = "reset" ] || [ "${1:-}" = "unset" ]; then
    unset LITELLM_API_KEY
    unset OPENROUTER_API_KEY
    unset ANTHROPIC_API_KEY
    unset ANTHROPIC_AUTH_TOKEN
    unset ANTHROPIC_BASE_URL
    unset ANTHROPIC_API_URL
    unset ANTHROPIC_MODEL
    unset ANTHROPIC_SMALL_FAST_MODEL
    unset ANTHROPIC_CUSTOM_MODEL_OPTION
    unset ANTHROPIC_CUSTOM_MODEL_OPTION_NAME
    unset ANTHROPIC_CUSTOM_MODEL_OPTION_DESCRIPTION
    unset ANTHROPIC_DEFAULT_OPUS_MODEL
    unset ANTHROPIC_DEFAULT_OPUS_MODEL_NAME
    unset ANTHROPIC_DEFAULT_OPUS_MODEL_DESCRIPTION
    unset ANTHROPIC_DEFAULT_OPUS_MODEL_SUPPORTED_CAPABILITIES
    unset ANTHROPIC_DEFAULT_SONNET_MODEL
    unset ANTHROPIC_DEFAULT_SONNET_MODEL_NAME
    unset ANTHROPIC_DEFAULT_SONNET_MODEL_DESCRIPTION
    unset ANTHROPIC_DEFAULT_SONNET_MODEL_SUPPORTED_CAPABILITIES
    unset ANTHROPIC_DEFAULT_HAIKU_MODEL
    unset ANTHROPIC_DEFAULT_HAIKU_MODEL_NAME
    unset ANTHROPIC_DEFAULT_HAIKU_MODEL_DESCRIPTION
    unset ANTHROPIC_DEFAULT_HAIKU_MODEL_SUPPORTED_CAPABILITIES
    unset CLAUDE_CODE_SUBAGENT_MODEL
    unset CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY
    unset CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS
    unset NO_PROXY
    unset DISABLE_TELEMETRY
    unset DISABLE_COST_WARNINGS
    unset API_TIMEOUT_MS

    echo "Claude Code LiteLLM environment cleared for this shell."
    echo "Now run: claude"
    echo "Then inside Claude Code run: /model default"
    return 0
  fi

  local LITELLM_DIR="$HOME/vibecode/litellm"

  if [ -f "$LITELLM_DIR/.env" ]; then
    set -a
    # shellcheck source=/dev/null
    source "$LITELLM_DIR/.env"
    set +a
  fi

  local LITELLM_URL
  if ! LITELLM_URL=$(litellm_base_url); then
    return 1
  fi

  local LITELLM_KEY="${LITELLM_MASTER_KEY:-}"
  if [ -z "$LITELLM_KEY" ]; then
    echo "Set LITELLM_MASTER_KEY in $LITELLM_DIR/.env" >&2
    return 1
  fi

  echo "🌐 LiteLLM proxy URL: $LITELLM_URL"

  local models=(
    'codex-5.5(xhigh)'             
    'codex-5.5(high)'              
    'codex-5.5(medium)'            
    'codex-5.4(xhigh)'             
    'codex-5.4(high)'              
    'codex-5.4(medium)'            
    'codex-5.4-mini(xhigh)'        
    'codex-5.4-mini(high)'         
    'codex-5.4-mini(medium)'       
    'codex-5.3-codex(xhigh)'       
    'codex-5.3-codex(high)'        
    'codex-5.3-codex(medium)'      
    'codex-5.3-codex-spark(xhigh)' 
    'codex-5.3-codex-spark(high)'  
    'codex-5.3-codex-spark(medium)'
    'codex-5.2(xhigh)'             
    'codex-5.2(high)'              
    'codex-5.2(medium)'            
    'codex-5.5(xhigh-fast)'        
    'codex-5.5(high-fast)'         
    'codex-5.4(xhigh-fast)'        
    'codex-5.4(high-fast)'         
    'codex-5.3-codex(xhigh-fast)'  
    'codex-5.3-codex(high-fast)'   
    'or-minimax-m3'                
    'or-minimax-m2.7'              
    'or-kimi-k2.6'                 
    'or-kimi-k2.5'                 
    'or-glm-5'                     
    'or-glm-5.1'                   
    'or-glm-4.7'                   
    'or-qwen3.7-max'               
    'or-qwen3.6-plus'              
    'or-qwen3.5-plus'              
    'or-qwen3.5-397b'              
    'or-qwen3-coder-next'          
    'or-qwen3.5-flash-free'        
    'glm-5.1:cloud'                
    'minimax-m2.7:cloud'           
    'minimax-m3:cloud'             
    'qwen3.5:397b-cloud'           
    'kimi-k2.6:cloud'              
    'kimi-k2.5:cloud'              
  )

  local model=""
  if [ -n "${1:-}" ]; then
    model="$1"
  else
    echo "Select a LiteLLM model_name (or Ctrl-C to cancel):"
    select model in "${models[@]}"; do
      if [ -n "$model" ]; then
        break
      fi
      echo "Invalid selection."
    done
  fi

  if [ -z "$model" ]; then
    echo "No model selected."
    return 1
  fi

  unset ANTHROPIC_DEFAULT_OPUS_MODEL_SUPPORTED_CAPABILITIES
  unset ANTHROPIC_DEFAULT_SONNET_MODEL_SUPPORTED_CAPABILITIES
  unset ANTHROPIC_DEFAULT_HAIKU_MODEL_SUPPORTED_CAPABILITIES
  unset CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY
  export CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1
  export CLAUDE_CODE_SUBAGENT_MODEL="inherit"

  if [[ "$model" == codex-* ]]; then
    export ANTHROPIC_BASE_URL="$LITELLM_URL"
    export ANTHROPIC_AUTH_TOKEN="$LITELLM_KEY"
    unset LITELLM_API_KEY
    unset ANTHROPIC_API_KEY
    unset ANTHROPIC_API_URL

    export ANTHROPIC_MODEL="$model"
    export ANTHROPIC_DEFAULT_OPUS_MODEL="$model"
    export ANTHROPIC_DEFAULT_OPUS_MODEL_NAME="$model"
    export ANTHROPIC_DEFAULT_OPUS_MODEL_DESCRIPTION="LiteLLM -> CLIProxyAPI Codex"
    export ANTHROPIC_DEFAULT_SONNET_MODEL="$model"
    export ANTHROPIC_DEFAULT_SONNET_MODEL_NAME="$model"
    export ANTHROPIC_DEFAULT_SONNET_MODEL_DESCRIPTION="LiteLLM -> CLIProxyAPI Codex"
    export ANTHROPIC_DEFAULT_HAIKU_MODEL="$model"
    export ANTHROPIC_DEFAULT_HAIKU_MODEL_NAME="$model"
    export ANTHROPIC_DEFAULT_HAIKU_MODEL_DESCRIPTION="LiteLLM -> CLIProxyAPI Codex"

    export ANTHROPIC_SMALL_FAST_MODEL="$model"
    export ANTHROPIC_CUSTOM_MODEL_OPTION="$model"
    export ANTHROPIC_CUSTOM_MODEL_OPTION_NAME="$model"
    export ANTHROPIC_CUSTOM_MODEL_OPTION_DESCRIPTION="LiteLLM -> CLIProxyAPI Codex"

    echo "Claude Code is configured directly for LiteLLM Codex."
    echo "Base: ${LITELLM_URL}"
    echo "Model: $model"
    echo ""
    echo "Run claude in this same shell."
    echo "Use /model default, opus, sonnet, haiku, or pick \"$model\" from the custom entry."
    return 0
  fi

  if ! command -v ccr >/dev/null 2>&1; then
    echo "ccr is required for non-codex models. Install/start Claude Code Router, then retry." >&2
    return 1
  fi

  export LITELLM_API_KEY="$LITELLM_KEY"
  unset ANTHROPIC_API_KEY
  unset ANTHROPIC_AUTH_TOKEN
  unset ANTHROPIC_BASE_URL
  unset ANTHROPIC_API_URL

  mkdir -p "$HOME/.claude-code-router"
  cat > "$HOME/.claude-code-router/config.json" <<EOF
{
  "LOG": true,
  "LITELLM_API_KEY": "\${LITELLM_API_KEY}",
  "Providers": [
    {
      "name": "litellm",
      "api_base_url": "${LITELLM_URL}/v1/chat/completions",
      "api_key": "\${LITELLM_API_KEY}",
      "models": ["$model"],
      "transformer": { "use": ["openai"] }
    }
  ],
  "Router": {
    "default": "litellm,$model"
  }
}
EOF

  ccr restart >/dev/null 2>&1 || ccr start
  eval "$(ccr activate)"

  local ccr_model="litellm,$model"
  export ANTHROPIC_MODEL="$ccr_model"
  export ANTHROPIC_DEFAULT_OPUS_MODEL="$ccr_model"
  export ANTHROPIC_DEFAULT_OPUS_MODEL_NAME="$model"
  export ANTHROPIC_DEFAULT_OPUS_MODEL_DESCRIPTION="CCR -> LiteLLM"
  export ANTHROPIC_DEFAULT_SONNET_MODEL="$ccr_model"
  export ANTHROPIC_DEFAULT_SONNET_MODEL_NAME="$model"
  export ANTHROPIC_DEFAULT_SONNET_MODEL_DESCRIPTION="CCR -> LiteLLM"
  export ANTHROPIC_DEFAULT_HAIKU_MODEL="$ccr_model"
  export ANTHROPIC_DEFAULT_HAIKU_MODEL_NAME="$model"
  export ANTHROPIC_DEFAULT_HAIKU_MODEL_DESCRIPTION="CCR -> LiteLLM"
  export ANTHROPIC_SMALL_FAST_MODEL="$ccr_model"
  export ANTHROPIC_CUSTOM_MODEL_OPTION="$ccr_model"
  export ANTHROPIC_CUSTOM_MODEL_OPTION_NAME="$model"
  export ANTHROPIC_CUSTOM_MODEL_OPTION_DESCRIPTION="CCR -> LiteLLM"

  echo "Claude Code Router is configured for LiteLLM."
  echo "Base: ${LITELLM_URL}/v1"
  echo "Model: $model"
  echo ""
  echo "Run claude in this same shell."
  echo "Use /model default, opus, sonnet, haiku, or pick \"$model\" from the custom entry."
}



```
