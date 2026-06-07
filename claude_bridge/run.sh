#!/usr/bin/with-contenv bashio

export OPENCLAW_URL="$(bashio::config 'openclaw_url')"
export OPENCLAW_TOKEN="$(bashio::config 'openclaw_token')"
export HA_ENTITIES_MAX="$(bashio::config 'ha_entities_max')"
# SUPERVISOR_TOKEN is injected automatically by the HA supervisor

bashio::log.info "Starting Claude Bridge → ${OPENCLAW_URL}"
exec python3 /app/main.py
