import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { QRCodeSVG } from "qrcode.react";
import { ArrowRight, Github, CheckCircle2, Copy, Check } from "lucide-react";
import velocityLogo from "../assets/logo.png";


interface OnboardingProps {
    onComplete: () => void;
    serverStatus: {
        ip: string;
        hostname?: string;
        token: string;
    } | null;
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
    serverStatus,
    shortcutIosToLinuxUrl,
    shortcutBidirectionalUrl,
}: OnboardingProps) {
    const [step, setStep] = useState(1);
    const [copiedAddress, setCopiedAddress] = useState(false);
    const [copiedToken, setCopiedToken] = useState(false);

    const nextStep = () => setStep((prev) => Math.min(prev + 1, 4));

    const finish = () => {
        onComplete();
    };

    const hostname = serverStatus?.hostname || serverStatus?.ip || "Loading...";
    const fullAddress = hostname !== "Loading..." ? `http://${hostname}:8080` : "Loading...";
    const displayToken = serverStatus?.token || "...";

    const copyToClipboard = async (text: string, type: 'address' | 'token') => {
        try {
            await navigator.clipboard.writeText(text);
            if (type === 'address') {
                setCopiedAddress(true);
                setTimeout(() => setCopiedAddress(false), 2000);
            } else {
                setCopiedToken(true);
                setTimeout(() => setCopiedToken(false), 2000);
            }
        } catch (err) {
            console.error('Failed to copy:', err);
        }
    };

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
                                Your clipboard, synchronized across iOS and Linux.
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
                                iOS to Linux Setup
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
                                                onClick={() => copyToClipboard(fullAddress, 'address')}
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
                                                onClick={() => copyToClipboard(displayToken, 'token')}
                                                title="Copy token"
                                            >
                                                {copiedToken ? <Check size={14} /> : <Copy size={14} />}
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </motion.div>
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
                                Linux to iOS Setup
                            </motion.h2>
                            <motion.p className="onboarding-step-desc">
                                Now setup your Linux shortcut to receive data from your iPhone.
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
                                                onClick={() => copyToClipboard(fullAddress, 'address')}
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
                                                onClick={() => copyToClipboard(displayToken, 'token')}
                                                title="Copy token"
                                            >
                                                {copiedToken ? <Check size={14} /> : <Copy size={14} />}
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </motion.div>
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
                                    href="https://github.com/AlexMontesCS/Velocity-Bridge"
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
