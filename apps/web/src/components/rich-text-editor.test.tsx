import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const uploadImage = vi.fn();
vi.mock("@/features/cms/api", () => ({
  cmsApi: { uploadImage: (...args: unknown[]) => uploadImage(...args) },
}));

import { RichTextEditor } from "@/components/rich-text-editor";
import { ApiError } from "@/lib/api-client";

describe("RichTextEditor", () => {
  beforeEach(() => {
    uploadImage.mockReset();
  });

  it("renders the toolbar and the editable surface without crashing", async () => {
    render(<RichTextEditor value="Hello world" onChange={vi.fn()} />);
    expect(await screen.findByRole("button", { name: /bold/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /insert image/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /insert table/i })).toBeInTheDocument();
    expect(screen.getByText(/for equations/i)).toBeInTheDocument();
  });

  it("uploads a chosen image, prompts for required alt text, and inserts it", async () => {
    uploadImage.mockResolvedValue({ filename: "abc_x.png", url: "/api/v1/cms/images/abc_x.png" });
    const promptSpy = vi.spyOn(window, "prompt").mockReturnValue("A labeled diagram");
    const onChange = vi.fn();

    render(<RichTextEditor value="" onChange={onChange} />);
    const user = userEvent.setup();

    const file = new File(["fake-bytes"], "diagram.png", { type: "image/png" });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(input, file);

    await waitFor(() => expect(uploadImage).toHaveBeenCalledWith(file));
    await waitFor(() => expect(promptSpy).toHaveBeenCalled());
    // The image command fires onUpdate -> onChange with the inserted image
    // in the serialized Markdown.
    await waitFor(() => expect(onChange).toHaveBeenCalled());
    const lastCall = onChange.mock.calls.at(-1)?.[0] as string;
    expect(lastCall).toContain("A labeled diagram");
    expect(lastCall).toContain("abc_x.png");
  });

  it("does not insert the image and shows an error if alt text is left empty", async () => {
    uploadImage.mockResolvedValue({ filename: "abc_x.png", url: "/api/v1/cms/images/abc_x.png" });
    vi.spyOn(window, "prompt").mockReturnValue("");
    const onChange = vi.fn();

    render(<RichTextEditor value="" onChange={onChange} />);
    const user = userEvent.setup();

    const file = new File(["fake-bytes"], "diagram.png", { type: "image/png" });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(input, file);

    await waitFor(() => expect(uploadImage).toHaveBeenCalled());
    expect(await screen.findByText(/alt text is required/i)).toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalled();
  });

  it("shows an upload error without crashing when the upload fails", async () => {
    uploadImage.mockRejectedValue(new ApiError("Uploaded file is not a valid image", "INVALID_FILE_TYPE", 400));

    render(<RichTextEditor value="" onChange={vi.fn()} />);
    const user = userEvent.setup();

    // Declared as a PNG (matches the file input's accept filter, which
    // user-event enforces) but with garbage bytes -- exactly what a
    // corrupted or maliciously-renamed upload looks like from the
    // browser's side; the backend's Pillow decode is what actually
    // catches it, surfaced here as the rejected upload.
    const file = new File(["not really a png"], "corrupted.png", { type: "image/png" });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(input, file);

    expect(await screen.findByText(/not a valid image/i)).toBeInTheDocument();
  });
});
