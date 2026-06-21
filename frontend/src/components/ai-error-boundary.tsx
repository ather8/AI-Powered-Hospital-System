/**
 * AiErrorBoundary — React error boundary for AI-powered pages.
 *
 * AI pages (chatbot, summary, notes, clinical search) can fail for reasons
 * outside the user's control: a missing API key, the LLM provider being
 * rate-limited, a cold-start FAISS load failure, etc. Without an error
 * boundary, any uncaught exception in these trees produces a blank white
 * screen with no explanation.
 *
 * This boundary catches render errors and shows a friendly "AI features
 * unavailable" message so the rest of the app stays functional.
 *
 * Usage
 * -----
 *   <AiErrorBoundary feature="Triage Chatbot">
 *     <ChatbotPage />
 *   </AiErrorBoundary>
 */

import { Component, type ReactNode, type ErrorInfo } from "react";
import { AlertTriangle } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

interface Props {
  children: ReactNode;
  /** Human-readable name of the AI feature, shown in the fallback UI. */
  feature?: string;
}

interface State {
  hasError: boolean;
  errorMessage: string;
}

export class AiErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, errorMessage: "" };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, errorMessage: error.message };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // In production you'd send this to Sentry / your error tracker
    console.error("[AiErrorBoundary] Caught error:", error, info);
  }

  handleReset = () => {
    this.setState({ hasError: false, errorMessage: "" });
  };

  render() {
    if (this.state.hasError) {
      const feature = this.props.feature ?? "AI feature";
      return (
        <div className="flex flex-col items-center justify-center min-h-[40vh] p-8">
          <Alert variant="destructive" className="max-w-lg">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>{feature} unavailable</AlertTitle>
            <AlertDescription className="mt-2 space-y-2">
              <p>
                This feature could not load. This is usually caused by a missing
                AI provider key or a temporary service outage.
              </p>
              {this.state.errorMessage && (
                <p className="font-mono text-xs opacity-70 break-all">
                  {this.state.errorMessage}
                </p>
              )}
              <p className="text-xs">
                Check that <code>GEMINI_API_KEY</code> or{" "}
                <code>OPENAI_API_KEY</code> is set in{" "}
                <code>backend/.env</code> and restart the server.
              </p>
            </AlertDescription>
          </Alert>
          <Button
            variant="outline"
            size="sm"
            className="mt-4"
            onClick={this.handleReset}
          >
            Try again
          </Button>
        </div>
      );
    }

    return this.props.children;
  }
}
