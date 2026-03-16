import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { QRCodeSVG } from "qrcode.react";
import { ArrowRight, Github, CheckCircle2, Copy, Check } from "lucide-react";
import velocityLogo from "../assets/logo.png";

interface OnboardingProps {
    onComplete: () => void;
    connectionAddress: string;
    connectionToken: string;
    useManualConnection: boolean;
    manualAddress: string;
    manualToken: string;
    onToggleManual: (value: boolean) => void;
    onManualAddressChange: (value: string) => void;
    onManualTokenChange: (value: string) => void;
    onApplyManualToken: () => void;
    onApplyManualAddress: () => void;
    isSettingToken: boolean;
    isSettingAddress: boolean;
    shortcutIosToLinuxUrl: string;
    shortcutBidirectionalUrl: string;
}

const springTransition = {
    type: "spring" as const,
    stiffness: 200,
    damping: 25,
};

const staggerChildren = {
    hidden: { opacity: 0 },
    show: {
        opacity: 1,
        transition: {
            staggerChildren: 0.08,
        },
    },
};

export default function Onboarding({
    onComplete,
    connectionAddress,
    connectionToken,
    useManualConnection,
    manualAddress,
    manualToken,
    onToggleManual,
    onManualAddressChange,
    onManualTokenChange,
    onApplyManualToken,
    onApplyManualAddress,
    isSettingToken,
    isSettingAddress,
    shortcutIosToLinuxUrl,
    shortcutBidirectionalUrl,
}: OnboardingProps) {
    const [step, setStep] = useState(1);
    const [copiedAddress, setCopiedAddress] = useState(false);
    const [copiedToken, setCopiedToken] = useState(false);

    const nextStep = () => setStep((prev) => Math.min(prev + 1, 5));

    const finish = () => {
        onComplete();
    };

    const fullAddress = connectionAddress || "Loading...";
    const displayToken = connectionToken || "...";
    const detectedPortMatch = fullAddress.match(/:(\d+)(?:\D|$)/);
    const detectedPort = detectedPortMatch ? parseInt(detectedPortMatch[1], 10) : null;
    const isNonDefaultPort = detectedPort !== null && detectedPort !== 8080;

    const copyToClipboard = async (text: string, type: "address" | "token") => {
        try {
            await navigator.clipboard.writeText(text);
            if (type === "address") {
                setCopiedAddress(true);
                setTimeout(() => setCopiedAddress(false), 2000);
            } else {
                setCopiedToken(true);
                setTimeout(() => setCopiedToken(false), 2000);
            }
        } catch (err) {
            console.error("Failed to copy:", err);
        }
    };

    const manualSection = (
        <div className="manual-override-layout">
            <div className="connection-pill manual-override-panel">
                <div className="pill-field">
                    <span className="pill-label">Manual Override</span>
                    <div className="pill-value-row manual-input-row">
                        <input
                            type="checkbox"
                            checked={useManualConnection}
                            onChange={(e) => onToggleManual(e.target.checked)}
                        />
                        <span className="pill-value">Use custom address and token</span>
                    </div>
                </div>
                <div className="pill-field">
                    <span className="pill-label">Address</span>
                    <div className="pill-value-row manual-input-row">
                        <input
                            type="text"
                            value={useManualConnection ? manualAddress : fullAddress}
                            readOnly={!useManualConnection}
                            onChange={(e) => onManualAddressChange(e.target.value)}
                            className="manual-input"
                        />
                        <button
                            className="pill-copy-btn"
                            onClick={onApplyManualAddress}
                            disabled={!useManualConnection || !manualAddress.trim() || isSettingAddress}
                            title="Save address"
                        >
                            {isSettingAddress ? "Saving..." : "Save"}
                        </button>
                    </div>
                </div>
                <div className="pill-field">
                    <span className="pill-label">Token</span>
                    <div className="pill-value-row manual-input-row">
                        <input
                            type="text"
                            value={useManualConnection ? manualToken : displayToken}
                            readOnly={!useManualConnection}
                            onChange={(e) => onManualTokenChange(e.target.value)}
                            className="manual-input"
                        />
                        <button
                            className="pill-copy-btn"
                            onClick={onApplyManualToken}
                            disabled={!useManualConnection || !manualToken.trim() || isSettingToken}
                            title="Set token"
                        >
                            {isSettingToken ? "Setting..." : "Set"}
                        </button>
                    </div>
                </div>
            </div>
            <div className="manual-override-note">
                <div className="manual-override-note-title">Address Format</div>
                <p>Use http:// and include the port, for example http://arsh.local:{detectedPort ?? 8080}.</p>
                <p>If 8080 is unavailable, use the port shown above (currently {detectedPort ?? 8080}).</p>
            </div>
        </div>
    );

    return (
        <motion.div
            className="onboarding-overlay"
            initial={{ opacity: 1 }}
            animate={{ opacity: 1 }}
        >
            <AnimatePresence mode="wait">
                {step === 1 && (
                    <motion.div
                        key="step1"
                        initial={{ x: 100, opacity: 0 }}
                        animate={{ x: 0, opacity: 1 }}
                        exit={{ x: -100, opacity: 0 }}
                        transition={springTransition}
                        className="onboarding-step"
                    >
                        <motion.div
                            variants={staggerChildren}
                            initial="hidden"
                            animate="show"
                            className="onboarding-content"
                        >
                            <motion.img
                                src={velocityLogo}
                                alt="Velocity Bridge"
                                className="onboarding-logo"
                            />
                            <motion.h1 className="onboarding-title">
                                Welcome to Velocity Bridge
                            </motion.h1>
                            <motion.p className="onboarding-subtitle">
                                Your clipboard, synchronized across iOS and Windows.
                            </motion.p>
                            <button
                                onClick={nextStep}
                                className="onboarding-button"
                            >
                                Start Setup <ArrowRight size={20} />
                            </button>
                        </motion.div>
                    </motion.div>
                )}

                {step === 2 && (
                    <motion.div
                        key="step2"
                        initial={{ x: 100, opacity: 0 }}
                        animate={{ x: 0, opacity: 1 }}
                        exit={{ x: -100, opacity: 0 }}
                        transition={springTransition}
                        className="onboarding-step"
                    >
                        <motion.div
                            variants={staggerChildren}
                            initial="hidden"
                            animate="show"
                            className="onboarding-content"
                        >
                            <motion.h2 className="onboarding-step-title">
                                Port Setup Notice
                            </motion.h2>
                            <motion.p className="onboarding-step-desc">
                                Velocity Bridge uses port 8080 by default on Linux. On Windows, the app will use the first free port between 8080 and 8100.
                            </motion.p>
                            <div className="connection-pill" style={{ maxWidth: "520px" }}>
                                <div className="pill-field">
                                    <span className="pill-label">Current Address</span>
                                    <div className="pill-value-row">
                                        <span className="pill-value">{fullAddress}</span>
                                    </div>
                                </div>
                                {isNonDefaultPort ? (
                                    <div className="pill-field">
                                        <span className="pill-label">Action Required</span>
                                        <div className="pill-value-row">
                                            <span className="pill-value">Update your iOS shortcuts to use port {detectedPort}.</span>
                                        </div>
                                    </div>
                                ) : (
                                    <div className="pill-field">
                                        <span className="pill-label">Status</span>
                                        <div className="pill-value-row">
                                            <span className="pill-value">Port 8080 is in use by Velocity.</span>
                                        </div>
                                    </div>
                                )}
                            </div>
                            <button
                                onClick={nextStep}
                                className="onboarding-button"
                            >
                                Next <ArrowRight size={20} />
                            </button>
                        </motion.div>
                    </motion.div>
                )}

                {step === 3 && (
                    <motion.div
                        key="step3"
                        initial={{ x: 100, opacity: 0 }}
                        animate={{ x: 0, opacity: 1 }}
                        exit={{ x: -100, opacity: 0 }}
                        transition={springTransition}
                        className="onboarding-step"
                    >
                        <motion.div
                            variants={staggerChildren}
                            initial="hidden"
                            animate="show"
                            className="onboarding-content"
                        >
                            <motion.h2 className="onboarding-step-title">
                                iOS to Windows Setup
                            </motion.h2>
                            <motion.p className="onboarding-step-desc">
                                Scan this on your iPhone to start sending data to this PC.
                            </motion.p>
                            <motion.div className="onboarding-qr-section">
                                <div className="qr-box">
                                    <QRCodeSVG value={shortcutIosToLinuxUrl} size={200} />
                                </div>
                                <div className="connection-pill">
                                    <div className="pill-field">
                                        <span className="pill-label">Address</span>
                                        <div className="pill-value-row">
                                            <span className="pill-value">{fullAddress}</span>
                                            <button
                                                className="pill-copy-btn"
                                                onClick={() => copyToClipboard(fullAddress, "address")}
                                                title="Copy address"
                                            >
                                                {copiedAddress ? <Check size={14} /> : <Copy size={14} />}
                                            </button>
                                        </div>
                                    </div>
                                    <div className="pill-field">
                                        <span className="pill-label">Token</span>
                                        <div className="pill-value-row">
                                            <span className="pill-value">{displayToken}</span>
                                            <button
                                                className="pill-copy-btn"
                                                onClick={() => copyToClipboard(displayToken, "token")}
                                                title="Copy token"
                                            >
                                                {copiedToken ? <Check size={14} /> : <Copy size={14} />}
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </motion.div>
                            {manualSection}
                            <button
                                onClick={nextStep}
                                className="onboarding-button"
                            >
                                Next <ArrowRight size={20} />
                            </button>
                        </motion.div>
                    </motion.div>
                )}

                {step === 4 && (
                    <motion.div
                        key="step4"
                        initial={{ x: 100, opacity: 0 }}
                        animate={{ x: 0, opacity: 1 }}
                        exit={{ x: -100, opacity: 0 }}
                        transition={springTransition}
                        className="onboarding-step"
                    >
                        <motion.div
                            variants={staggerChildren}
                            initial="hidden"
                            animate="show"
                            className="onboarding-content"
                        >
                            <motion.h2 className="onboarding-step-title">
                                Windows to iOS Setup
                            </motion.h2>
                            <motion.p className="onboarding-step-desc">
                                Now setup your Windows shortcut to receive data from your iPhone.
                            </motion.p>
                            <motion.div className="onboarding-qr-section">
                                <div className="qr-box">
                                    <QRCodeSVG value={shortcutBidirectionalUrl} size={200} />
                                </div>
                                <div className="connection-pill">
                                    <div className="pill-field">
                                        <span className="pill-label">Address</span>
                                        <div className="pill-value-row">
                                            <span className="pill-value">{fullAddress}</span>
                                            <button
                                                className="pill-copy-btn"
                                                onClick={() => copyToClipboard(fullAddress, "address")}
                                                title="Copy address"
                                            >
                                                {copiedAddress ? <Check size={14} /> : <Copy size={14} />}
                                            </button>
                                        </div>
                                    </div>
                                    <div className="pill-field">
                                        <span className="pill-label">Token</span>
                                        <div className="pill-value-row">
                                            <span className="pill-value">{displayToken}</span>
                                            <button
                                                className="pill-copy-btn"
                                                onClick={() => copyToClipboard(displayToken, "token")}
                                                title="Copy token"
                                            >
                                                {copiedToken ? <Check size={14} /> : <Copy size={14} />}
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </motion.div>
                            {manualSection}
                            <button
                                onClick={nextStep}
                                className="onboarding-button"
                            >
                                Next <ArrowRight size={20} />
                            </button>
                        </motion.div>
                    </motion.div>
                )}

                {step === 5 && (
                    <motion.div
                        key="step5"
                        initial={{ x: 100, opacity: 0 }}
                        animate={{ x: 0, opacity: 1 }}
                        exit={{ x: -100, opacity: 0 }}
                        transition={springTransition}
                        className="onboarding-step"
                    >
                        <motion.div
                            variants={staggerChildren}
                            initial="hidden"
                            animate="show"
                            className="onboarding-content"
                        >
                            <motion.div className="success-icon">
                                <CheckCircle2 size={64} strokeWidth={1.5} />
                            </motion.div>
                            <motion.h2 className="onboarding-step-title">
                                You're All Set!
                            </motion.h2>
                            <motion.p className="onboarding-step-desc">
                                Thank you for using Velocity Bridge.
                            </motion.p>
                            <motion.div className="credits">
                                <p>
                                    Created by <strong>Arsh</strong>
                                </p>
                                <a
                                    href="https://github.com/Trex099/Velocity-Bridge"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="github-link"
                                >
                                    <Github size={16} />
                                    View on GitHub
                                </a>
                            </motion.div>
                            <button
                                onClick={finish}
                                className="onboarding-button"
                            >
                                Finish
                            </button>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>
        </motion.div>
    );
}
