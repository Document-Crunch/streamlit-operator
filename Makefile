# Makefile for Streamlit Operator
# Provides convenience commands for deploying and updating the Helm chart

# Default values - can be overridden with environment variables
NAMESPACE ?= streamlit
RELEASE_NAME ?= streamlit-operator
CHART_PATH ?= ./charts/streamlit-chart
VALUES_FILE ?= values.yaml
KUBE_CONTEXT ?= $(shell kubectl config current-context)

# Set to true to see Helm debug output
DEBUG ?= false

# Common Helm flags
HELM_FLAGS = --namespace $(NAMESPACE) --create-namespace
ifeq ($(DEBUG),true)
	HELM_FLAGS += --debug
endif

# Default target
.PHONY: help
help:
	@echo "Streamlit Operator Makefile"
	@echo ""
	@echo "Available commands:"
	@echo "  make install                   - Install Streamlit Operator with default values"
	@echo "  make upgrade                   - Upgrade existing installation with default values"
	@echo "  make uninstall                 - Uninstall Streamlit Operator"
	@echo "  make lint                      - Lint the Helm chart"
	@echo ""
	@echo "Environment variables:"
	@echo "  NAMESPACE     - Kubernetes namespace (default: streamlit)"
	@echo "  RELEASE_NAME  - Helm release name (default: streamlit-operator)"
	@echo "  VALUES_FILE   - Path to values file (default: values.yaml)"
	@echo "  DEBUG         - Enable Helm debug output (default: false)"
	@echo ""

# Install with default values
.PHONY: install
install:
	helm install $(RELEASE_NAME) $(CHART_PATH) $(HELM_FLAGS) -f $(VALUES_FILE)
# Upgrade with default values
.PHONY: upgrade
upgrade:
	helm upgrade $(RELEASE_NAME) $(CHART_PATH) $(HELM_FLAGS) -f $(VALUES_FILE)

# Uninstall Streamlit Operator
.PHONY: uninstall
uninstall:
	helm uninstall $(RELEASE_NAME) -n $(NAMESPACE)

# Lint the Helm chart
.PHONY: lint
lint:
	helm lint $(CHART_PATH) -f $(VALUES_FILE)
