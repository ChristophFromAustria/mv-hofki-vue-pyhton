FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

ARG TZ
ENV TZ="$TZ"


# Remove broken Yarn repo (expired GPG key in base image)
RUN rm -f /etc/apt/sources.list.d/yarn.list

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    tmux \
    libcairo2-dev \
    && rm -rf /var/lib/apt/lists/*

# Pre-install Python dependencies for faster rebuilds
COPY pyproject.toml /tmp/pyproject.toml
RUN pip install --no-cache-dir $(python3 -c "import tomllib,pathlib;d=tomllib.loads(pathlib.Path('/tmp/pyproject.toml').read_text());print(' '.join(d['project']['dependencies']+d['project']['optional-dependencies']['dev']))")

# Install Node.js LTS for frontend tooling
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Install Claude Code via native installer (as vscode user so it lands on their PATH)
USER vscode
RUN curl -fsSL https://claude.ai/install.sh | bash
USER root

# Persist bash history
RUN SNIPPET="export PROMPT_COMMAND='history -a' && export HISTFILE=/commandhistory/.bash_history" \
  && mkdir /commandhistory \
  && touch /commandhistory/.bash_history \
  && chown -R vscode /commandhistory \
  && echo "$SNIPPET" >> /home/vscode/.bashrc

# Create config directory for Claude
RUN mkdir -p /home/vscode/.claude && \
    chown -R vscode:vscode /home/vscode/.claude

# Expose API port
EXPOSE 8000

# Set devcontainer marker
ENV DEVCONTAINER=true

USER vscode

CMD ["sleep", "infinity"]
