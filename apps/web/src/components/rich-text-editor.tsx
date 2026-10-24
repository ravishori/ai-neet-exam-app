"use client";

import { useEffect, useRef, useState } from "react";
import { useEditor, EditorContent, type Editor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import TiptapImage from "@tiptap/extension-image";
import { Table } from "@tiptap/extension-table";
import TableRow from "@tiptap/extension-table-row";
import TableCell from "@tiptap/extension-table-cell";
import TableHeader from "@tiptap/extension-table-header";
import { Markdown } from "tiptap-markdown";
import {
  Bold,
  Italic,
  List,
  ListOrdered,
  Table as TableIcon,
  ImagePlus,
  Sigma,
  Loader2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { cmsApi } from "@/features/cms/api";
import { ApiError } from "@/lib/api-client";
import { cn } from "@/lib/utils";

/**
 * WYSIWYG editing surface over a plain Markdown string -- the storage/wire
 * format stays Markdown (already rendered everywhere via MarkdownRenderer,
 * see F-17-era commits), only the authoring experience is Tiptap. Content
 * leaves this component exclusively through tiptap-markdown's serializer
 * (editor.storage.markdown.getMarkdown()) -- editor.getHTML() is never
 * used for storage, so no raw HTML is ever persisted.
 *
 * Equations: typed directly as LaTeX delimited by $...$ / $$...$$ (no
 * dedicated math node/toolbar button) -- remark-math/rehype-katex on the
 * read side (MarkdownRenderer) already renders this correctly; adding a
 * live-preview math node is a larger dependency/UX surface left for a
 * later iteration, not required for equations to work end to end today.
 */

function ToolbarButton({
  onClick,
  active,
  disabled,
  label,
  children,
}: {
  onClick: () => void;
  active?: boolean;
  disabled?: boolean;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <Button
      type="button"
      size="icon"
      variant={active ? "default" : "outline"}
      disabled={disabled}
      onClick={onClick}
      aria-label={label}
      title={label}
      className="size-7"
    >
      {children}
    </Button>
  );
}

function Toolbar({ editor, uploading, onUploadClick }: { editor: Editor; uploading: boolean; onUploadClick: () => void }) {
  return (
    <div className="flex flex-wrap items-center gap-1 border-b bg-muted/40 p-1">
      <ToolbarButton
        label="Bold"
        active={editor.isActive("bold")}
        onClick={() => editor.chain().focus().toggleBold().run()}
      >
        <Bold className="size-4" />
      </ToolbarButton>
      <ToolbarButton
        label="Italic"
        active={editor.isActive("italic")}
        onClick={() => editor.chain().focus().toggleItalic().run()}
      >
        <Italic className="size-4" />
      </ToolbarButton>
      <ToolbarButton
        label="Bullet list"
        active={editor.isActive("bulletList")}
        onClick={() => editor.chain().focus().toggleBulletList().run()}
      >
        <List className="size-4" />
      </ToolbarButton>
      <ToolbarButton
        label="Numbered list"
        active={editor.isActive("orderedList")}
        onClick={() => editor.chain().focus().toggleOrderedList().run()}
      >
        <ListOrdered className="size-4" />
      </ToolbarButton>
      <ToolbarButton
        label="Insert table"
        onClick={() => editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()}
      >
        <TableIcon className="size-4" />
      </ToolbarButton>
      <ToolbarButton label="Insert image" disabled={uploading} onClick={onUploadClick}>
        {uploading ? <Loader2 className="size-4 animate-spin" /> : <ImagePlus className="size-4" />}
      </ToolbarButton>
      <span className="ml-1 inline-flex items-center gap-1 text-xs text-muted-foreground" title="Type $...$ for inline equations, $$...$$ for block equations">
        <Sigma className="size-3.5" />
        $...$ for equations
      </span>
    </div>
  );
}

export function RichTextEditor({
  value,
  onChange,
  placeholder,
  className,
}: {
  value: string;
  onChange: (markdown: string) => void;
  placeholder?: string;
  className?: string;
}) {
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const lastEmitted = useRef(value);

  const editor = useEditor({
    extensions: [
      StarterKit,
      TiptapImage,
      Table.configure({ resizable: false }),
      TableRow,
      TableHeader,
      TableCell,
      Markdown.configure({ html: false, transformPastedText: true }),
    ],
    content: value,
    editorProps: {
      attributes: {
        class: cn(
          "prose prose-sm sm:prose-base dark:prose-invert max-w-none min-h-32 p-3 focus:outline-none",
        ),
      },
    },
    onUpdate: ({ editor: ed }) => {
      const markdownStorage = (ed.storage as unknown as Record<string, { getMarkdown: () => string }>).markdown;
      const markdown = markdownStorage.getMarkdown();
      lastEmitted.current = markdown;
      onChange(markdown);
    },
    immediatelyRender: false,
  });

  // Keep the editor in sync if `value` changes from outside (e.g. the
  // containing form resets on Cancel/reopen) without fighting the user's
  // own typing -- only resets when the incoming value didn't originate
  // from this editor's own last onChange emission.
  useEffect(() => {
    if (!editor || value === lastEmitted.current) return;
    editor.commands.setContent(value);
    lastEmitted.current = value;
  }, [value, editor]);

  async function handleFileChosen(file: File) {
    setUploadError(null);
    setUploading(true);
    try {
      const { url } = await cmsApi.uploadImage(file);
      const alt = window.prompt("Alt text (required, describes the image for accessibility/screen readers):", "") ?? "";
      if (!alt.trim()) {
        setUploadError("Image not inserted: alt text is required.");
        return;
      }
      const { API_URL } = await import("@/lib/api-client");
      editor?.chain().focus().setImage({ src: `${API_URL}${url}`, alt: alt.trim() }).run();
    } catch (err) {
      setUploadError(err instanceof ApiError ? err.message : "Image upload failed.");
    } finally {
      setUploading(false);
    }
  }

  if (!editor) return null;

  return (
    <div className={cn("rounded-md border bg-background", className)}>
      <Toolbar editor={editor} uploading={uploading} onUploadClick={() => fileInputRef.current?.click()} />
      <input
        ref={fileInputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          if (file) void handleFileChosen(file);
        }}
      />
      {uploadError && <p className="px-3 pt-2 text-xs text-destructive">{uploadError}</p>}
      <EditorContent editor={editor} placeholder={placeholder} />
    </div>
  );
}
