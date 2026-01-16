[![CI](https://github.com/PenguinCloud/project-template/actions/workflows/ci.yml/badge.svg)](https://github.com/PenguinCloud/project-template/actions/workflows/ci.yml)
[![Docker Build](https://github.com/PenguinCloud/project-template/actions/workflows/docker-build.yml/badge.svg)](https://github.com/PenguinCloud/project-template/actions/workflows/docker-build.yml)
[![codecov](https://codecov.io/gh/PenguinCloud/project-template/branch/main/graph/badge.svg)](https://codecov.io/gh/PenguinCloud/project-template)
[![Go Report Card](https://goreportcard.com/badge/github.com/PenguinCloud/project-template)](https://goreportcard.com/report/github.com/PenguinCloud/project-template)
[![version](https://img.shields.io/badge/version-5.1.1-blue.svg)](https://semver.org)
[![License](https://img.shields.io/badge/License-Limited%20AGPL3-blue.svg)](LICENSE.md)

<div align="center">
  <img src="docs/screenshots/logo.png" alt="Current Logo" width="400"/>

  <h1>Current - URL Shortener & Management Platform</h1>
  <p><em>Fast, Secure, Enterprise-Ready URL Shortening</em></p>
</div>

```
  _____ _   _ ____  ____  _____ _   _ _____
 / ____| | | |  _ \|  _ \| ____| \ | |_   _|
| |    | | | | |_) | |_) |  _| |  \| | | |
| |    | |_| |  _ <|  _ <| |___| |\  | | |
 \____|\___/|_| \_\_| \_\_____|_| \_| |_|

```

# Current - URL Shortener & Management Platform

A comprehensive URL shortener and management platform with enterprise features including custom aliases, analytics tracking, QR code generation, and role-based access control. Built with a modern three-container microservices architecture for scalability and performance.
## ✨ Why Choose This Template?

### 🏭 Enterprise-Ready Architecture
Built for production from day one with multi-language support (Go 1.24+, Python 3.12/3.13, Node.js 18+), comprehensive CI/CD pipelines, and enterprise-grade security scanning.

### 🔒 Security First
- **8-stage security validation** including Trivy, CodeQL, and Semgrep scanning
- **TLS 1.2 minimum enforcement**, preferring TLS 1.3
- **Automated vulnerability detection** with Dependabot and Socket.dev integration
- **Secrets management** with environment-based configuration

### 🚀 Performance Optimized
- **Multi-architecture Docker builds** (amd64/arm64) with Debian-slim base images
- **Parallel CI/CD workflows** for optimized build times
- **eBPF/XDP networking** support for high-performance applications
- **Connection pooling** and caching strategies built-in

### 🏢 PenguinTech License Server Integration
- **Centralized feature gating** with `https://license.penguintech.io`
- **Universal JSON response format** across all products
- **Multi-tier licensing** (community/professional/enterprise)
- **Usage tracking and compliance** reporting

### 🔄 Self-Healing & Monitoring
- **Built-in health checks** and self-healing capabilities
- **Prometheus metrics** and Grafana dashboard integration
- **Structured logging** with configurable verbosity levels
- **Real-time monitoring** and alerting

### 🌐 Multi-Environment Support
- **Air-gapped deployment** ready with local caching
- **Container orchestration** with Kubernetes and Helm
- **Environment-specific configurations** for dev/staging/production
- **Blue-green deployment** support with automated rollbacks

## 🛠️ Quick Start

```bash
# Clone and setup
git clone <your-repository-url>
cd your-project
make setup                    # Install dependencies and setup environment
make dev                      # Start development environment
```

## 📚 Key Components

### Core Technologies
- **Languages**: Go 1.24+, Python 3.12/3.13, Node.js 18+
- **Databases**: PostgreSQL with PyDAL/GORM, Redis/Valkey caching
- **Containers**: Docker with multi-stage builds, Kubernetes deployment
- **Monitoring**: Prometheus, Grafana, structured logging

### Security Features
- Multi-factor authentication (MFA) and JWT tokens
- Role-based access control (RBAC)
- Automated security scanning and vulnerability management
- Compliance audit logging (SOC2, ISO27001 ready)

### Development Workflow
- Comprehensive test coverage (unit, integration, e2e)
- Automated code quality checks (linting, formatting, type checking)
- Version management with semantic versioning
- Feature branch workflow with required reviews

## 📖 Documentation

- **Getting Started**: [docs/development/](docs/development/)
- **API Reference**: [docs/api/](docs/api/)
- **Deployment Guide**: [docs/deployment/](docs/deployment/)
- **Architecture Overview**: [docs/architecture/](docs/architecture/)
- **License Integration**: [docs/licensing/](docs/licensing/)

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Maintainers
- **Primary**: creatorsemailhere@penguintech.group
- **General**: info@penguintech.group
- **Company**: [www.penguintech.io](https://www.penguintech.io)

### Community Contributors
- *Your name could be here! Submit a PR to get started.*

## 📞 Support & Resources

- **Documentation**: [./docs/](docs/)
- **Premium Support**: https://support.penguintech.group
- **Community Issues**: [GitHub Issues](../../issues)
- **License Server Status**: https://status.penguintech.io

## 📄 License

This project is licensed under the Limited AGPL3 with preamble for fair use - see [LICENSE.md](docs/LICENSE.md) for details.

**License Highlights:**
- **Personal & Internal Use**: Free under AGPL-3.0
- **Commercial Use**: Requires commercial license
- **SaaS Deployment**: Requires commercial license if providing as a service

### Contributor Employer Exception (GPL-2.0 Grant)

Companies employing official contributors receive GPL-2.0 access to community features:

- **Perpetual for Contributed Versions**: GPL-2.0 rights to versions where the employee contributed remain valid permanently, even after the employee leaves the company
- **Attribution Required**: Employee must be credited in CONTRIBUTORS, AUTHORS, commit history, or release notes
- **Future Versions**: New versions released after employment ends require standard licensing
- **Community Only**: Enterprise features still require a commercial license

This exception rewards contributors by providing lasting fair use rights to their employers. See [LICENSE.md](docs/LICENSE.md) for full terms.
