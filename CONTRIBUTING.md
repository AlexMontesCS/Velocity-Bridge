# Contributing to Velocity Bridge

Contributions to the development and maintenance of Velocity Bridge are welcome.

## Development Setup

The project utilizes a dual-stack architecture consisting of a Tauri/Rust frontend and a Python-based sidecar service.

### Prerequisites
- [Rust](https://www.rust-lang.org/) (current stable version)
- [Node.js](https://nodejs.org/) (LTS)
- [Python 3.10+](https://www.python.org/)

### Local Development Environment
1. **Repository Initialization**:
   ```bash
   git clone https://github.com/AlexMontesCS/Velocity-Bridge.git
   cd Velocity-Bridge/Velocity_GUI
   ```

2. **Frontend Dependencies**:
   ```bash
   npm install
   ```

3. **Backend Service Initialization**:
   Ensure the Python dependencies are installed for the sidecar located in `src-python/`.

4. **Execution**:
   Start the development server:
   ```bash
   npm run tauri dev
   ```

## Contribution workflow

1. **Issue Tracking**: Verify existing issues or open a new one to discuss proposed changes.
2. **Branching**: Create a feature-specific branch for your modifications.
3. **Verification**: Validate all changes across supported Linux distributions (e.g., Fedora, Ubuntu) before submission.
4. **Pull Requests**: Submit a comprehensive pull request detailing the modifications and their technical rationale.

## Standards and Guidelines

- Maintain technical clarity and provide relevant comments within complex logic.
- Ensure all new features are documented within the corresponding sections of the README.
- Verify that cryptographic signing configurations remain unmodified unless explicitly required.

---

For technical inquiries, please utilize the official issue tracker.
