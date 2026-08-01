"use client";

import { memo, useRef, useState, type ComponentPropsWithoutRef, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeHighlight from "rehype-highlight";
import {
  BookOpen,
  Lightbulb,
  Layers,
  Calculator,
  Image as ImageIcon,
  FlaskConical,
  Star,
  TriangleAlert,
  MessageCircleQuestion,
  Bookmark,
  ClipboardList,
  HelpCircle,
  Hash,
  Copy,
  Check,
  type LucideIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";
import "katex/dist/katex.min.css";

const SECTION_ICONS: { match: RegExp; icon: LucideIcon }[] = [
  { match: /definition/i, icon: BookOpen },
  { match: /key concepts?/i, icon: Lightbulb },
  { match: /core principles?/i, icon: Layers },
  { match: /formulae|formula/i, icon: Calculator },
  { match: /diagrams?/i, icon: ImageIcon },
  { match: /examples?/i, icon: FlaskConical },
  { match: /neet tips?|tricks?/i, icon: Star },
  { match: /common mistakes?/i, icon: TriangleAlert },
  { match: /frequently asked|faqs?/i, icon: MessageCircleQuestion },
  { match: /quick revision/i, icon: Bookmark },
  { match: /practice mcqs?/i, icon: ClipboardList },
];

function iconForHeading(text: string): LucideIcon {
  return SECTION_ICONS.find((s) => s.match.test(text))?.icon ?? Hash;
}

function textContent(node: ReactNode): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(textContent).join("");
  return "";
}

function CodeBlock({ children }: { children?: ReactNode }) {
  const preRef = useRef<HTMLPreElement>(null);
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    const text = preRef.current?.textContent ?? "";
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="group/code relative">
      <button
        type="button"
        aria-label={copied ? "Copied" : "Copy code"}
        onClick={handleCopy}
        className="absolute top-2 right-2 rounded-md border bg-card/90 p-1.5 text-muted-foreground opacity-0 transition-opacity group-hover/code:opacity-100 hover:text-foreground focus-visible:opacity-100"
      >
        {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
      </button>
      <pre ref={preRef} className="scroll-thin overflow-x-auto rounded-lg bg-muted p-4 text-sm">
        {children}
      </pre>
    </div>
  );
}

const components: Components = {
  h1: ({ children }) => (
    <h1 className="mt-0 mb-4 border-b pb-3 text-2xl font-bold tracking-tight text-balance">{children}</h1>
  ),
  h2: ({ children }) => {
    const Icon = iconForHeading(textContent(children));
    return (
      <h2 className="mt-8 mb-3 flex items-center gap-2 text-lg font-semibold first:mt-0">
        <Icon className="size-4.5 shrink-0 text-primary" aria-hidden="true" />
        {children}
      </h2>
    );
  },
  h3: ({ children }) => (
    <h3 className="mt-6 mb-2 flex items-center gap-2 text-base font-semibold">
      <HelpCircle className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      {children}
    </h3>
  ),
  hr: () => <hr className="my-6 border-border" />,
  p: ({ children }) => <p className="mb-3 leading-relaxed last:mb-0">{children}</p>,
  ul: ({ children }) => <ul className="mb-3 ml-5 list-disc space-y-1 marker:text-muted-foreground">{children}</ul>,
  ol: ({ children }) => <ol className="mb-3 ml-5 list-decimal space-y-1 marker:text-muted-foreground">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  blockquote: ({ children }) => (
    <blockquote className="my-4 rounded-r-md border-l-4 border-primary bg-primary/5 py-2 pl-4 text-sm text-foreground/90 italic">
      {children}
    </blockquote>
  ),
  table: ({ children }) => (
    <div className="scroll-thin mb-4 overflow-x-auto rounded-lg border">
      <table className="w-full border-collapse text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-muted/60">{children}</thead>,
  th: ({ children }) => <th className="border-b px-3 py-2 text-left font-semibold">{children}</th>,
  td: ({ children }) => <td className="border-b px-3 py-2 align-top">{children}</td>,
  a: ({ children, href }) => (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="font-medium text-primary underline underline-offset-2 hover:text-primary/80"
    >
      {children}
    </a>
  ),
  strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
  code: ({ className, children, ...props }: ComponentPropsWithoutRef<"code">) => {
    const isBlock = /language-/.test(className ?? "");
    if (!isBlock) {
      return (
        <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-[0.85em]" {...props}>
          {children}
        </code>
      );
    }
    return (
      <code className={className} {...props}>
        {children}
      </code>
    );
  },
  pre: ({ children }) => <CodeBlock>{children}</CodeBlock>,
};

export const MarkdownRenderer = memo(function MarkdownRenderer({ content, className }: { content: string; className?: string }) {
  return (
    <div className={cn("prose prose-tutor prose-sm max-w-none sm:prose-base dark:prose-invert", className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex, rehypeHighlight]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
});
