FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

# LK-10 only needs Debian packages. The inherited Yarn repository can have
# an expired signing key and prevent Docker/SSH features from installing.
RUN if [ -f /etc/apt/sources.list.d/yarn.list ]; then \
      mv /etc/apt/sources.list.d/yarn.list /etc/apt/yarn.list.disabled; \
    fi
