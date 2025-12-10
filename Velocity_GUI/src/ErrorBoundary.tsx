import { Component, ErrorInfo, ReactNode } from "react";

interface Props {
    children: ReactNode;
}

interface State {
    hasError: boolean;
    error: Error | null;
}

class ErrorBoundary extends Component<Props, State> {
    constructor(props: Props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error("ErrorBoundary caught an error:", error, errorInfo);
    }

    render() {
        if (this.state.hasError) {
            return (
                <div style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    justifyContent: "center",
                    height: "100vh",
                    backgroundColor: "#1e1e1e",
                    color: "#fff",
                    padding: "40px",
                    textAlign: "center",
                    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif"
                }}>
                    <h1 style={{ fontSize: "48px", marginBottom: "16px" }}>⚠️</h1>
                    <h2 style={{ fontSize: "24px", fontWeight: 600, marginBottom: "8px" }}>
                        Something went wrong
                    </h2>
                    <p style={{ color: "#888", marginBottom: "24px", maxWidth: "400px" }}>
                        Velocity Bridge encountered an unexpected error. Try restarting the application.
                    </p>
                    <pre style={{
                        background: "#2d2d2d",
                        padding: "16px",
                        borderRadius: "8px",
                        fontSize: "12px",
                        color: "#ff6b6b",
                        maxWidth: "600px",
                        overflow: "auto",
                        textAlign: "left"
                    }}>
                        {this.state.error?.message || "Unknown error"}
                    </pre>
                    <button
                        onClick={() => window.location.reload()}
                        style={{
                            marginTop: "24px",
                            padding: "12px 24px",
                            background: "#007AFF",
                            color: "#fff",
                            border: "none",
                            borderRadius: "8px",
                            fontSize: "14px",
                            fontWeight: 500,
                            cursor: "pointer"
                        }}
                    >
                        Reload App
                    </button>
                </div>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
