FROM python:3.13-slim-bookworm AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Version comes from the git tag via CI (build-arg); .git is not in the build
# context, so setuptools-scm reads this pretend-version instead. The 0.0.0
# fallback keeps non-release/local builds working without a tag.
ARG SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0
ENV SETUPTOOLS_SCM_PRETEND_VERSION_FOR_SGR_AGENT_CORE=${SETUPTOOLS_SCM_PRETEND_VERSION}

# Install build dependencies
RUN apt update \
 && apt install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml MANIFEST.in README.md LICENSE ./
COPY sgr_agent_core/ ./sgr_agent_core/
COPY examples/ ./examples/

# Install package from root
RUN pip install --no-cache-dir .

# Remove build dependencies
RUN apt purge -y build-essential \
 && apt autoremove -y \
 && rm -rf /var/lib/apt/lists/*


FROM python:3.13-slim-bookworm AS runner

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PATH="/usr/local/bin:$PATH"

# Install runtime dependencies (bubblewrap for RunCommandTool safe mode)
RUN apt update \
 && apt install -y --no-install-recommends curl ca-certificates bubblewrap \
 && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1000 sgrgroup \
 && useradd --no-create-home --shell /bin/false --uid 1000 --gid 1000 --system sgruser

# Copy installed package from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy configuration files and examples module
WORKDIR /app
COPY --chown=sgruser:sgrgroup examples/ ./examples/
COPY --chown=sgruser:sgrgroup logging_config.yaml ./logging_config.yaml

# Use config from examples/sgr_deep_research
ENV CONFIG_FILE=/app/examples/sgr_deep_research/config.yaml

# Create directories for logs and reports
RUN mkdir -p logs reports \
 && chown -R sgruser:sgrgroup /app

USER sgruser:sgrgroup

# Expose port
EXPOSE 8010

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8010/health || exit 1

# Run sgr command with sgr_deep_research configuration
ENTRYPOINT ["sgr", "--config-file", "/app/config.yaml", "--host", "0.0.0.0", "--port", "8010"]
