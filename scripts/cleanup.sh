#!/bin/bash
# ══════════════════════════════════════════════════════════
# MEL Demo — Complete Cleanup Script
# 
# Removes all demo components and restores VPS to
# its pre-demo state. Does NOT touch n8n or other
# existing services.
#
# Usage: chmod +x scripts/cleanup.sh && ./scripts/cleanup.sh
# ══════════════════════════════════════════════════════════

set -e

echo ""
echo "═══════════════════════════════════════════"
echo "  MEL Demo — Cleanup"
echo "═══════════════════════════════════════════"
echo ""

# ── Step 1: Remove MEL application ──
echo "[1/5] Removing MEL application..."
if command -v helm &> /dev/null; then
    helm uninstall mel -n mel-demo 2>/dev/null && echo "  ✓ Helm release 'mel' removed" || echo "  – Already removed"
fi
kubectl delete namespace mel-demo 2>/dev/null && echo "  ✓ Namespace 'mel-demo' deleted" || echo "  – Namespace already gone"
echo ""

# ── Step 2: Remove monitoring stack ──
echo "[2/5] Removing monitoring stack..."
if command -v helm &> /dev/null; then
    helm uninstall grafana -n monitoring 2>/dev/null && echo "  ✓ Grafana removed" || echo "  – Grafana already removed"
    helm uninstall prometheus -n monitoring 2>/dev/null && echo "  ✓ Prometheus removed" || echo "  – Prometheus already removed"
fi
kubectl delete namespace monitoring 2>/dev/null && echo "  ✓ Namespace 'monitoring' deleted" || echo "  – Namespace already gone"
echo ""

# ── Step 3: Uninstall k3s ──
echo "[3/5] Uninstalling k3s..."
if [ -f /usr/local/bin/k3s-uninstall.sh ]; then
    /usr/local/bin/k3s-uninstall.sh
    echo "  ✓ k3s removed completely"
else
    echo "  – k3s not installed, skipping"
fi
echo ""

# ── Step 4: Remove Helm binary ──
echo "[4/5] Removing Helm..."
if [ -f /usr/local/bin/helm ]; then
    rm -f /usr/local/bin/helm
    echo "  ✓ Helm binary removed"
else
    echo "  – Helm not found, skipping"
fi
echo ""

# ── Step 5: Clean up Docker images ──
echo "[5/5] Removing demo Docker images..."
docker rmi mel-edge-service:latest 2>/dev/null && echo "  ✓ mel-edge-service image removed" || echo "  – Image already removed"
docker rmi mel-sensor-simulator:latest 2>/dev/null && echo "  ✓ mel-sensor-simulator image removed" || echo "  – Image already removed"
echo ""

# ── Done ──
echo "═══════════════════════════════════════════"
echo "  ✓ Cleanup complete!"
echo ""
echo "  Your VPS is restored to pre-demo state."
echo "  Existing services (n8n, etc.) are untouched."
echo "═══════════════════════════════════════════"
echo ""
echo "Verify your existing services still work:"
echo "  docker ps"
echo "  curl -s -o /dev/null -w '%{http_code}' http://localhost:80"
echo ""