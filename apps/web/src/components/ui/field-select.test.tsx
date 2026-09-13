import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import { FieldSelect } from "@/components/ui/field-select";

describe("FieldSelect (Phase A5 canonical native <select>)", () => {
  it("renders a native <select> with the data-slot handle", () => {
    render(
      <FieldSelect aria-label="fs">
        <option value="a">A</option>
      </FieldSelect>,
    );
    const el = screen.getByLabelText("fs");
    expect(el.tagName).toBe("SELECT");
    expect(el.getAttribute("data-slot")).toBe("field-select");
  });

  it("renders every option child", () => {
    render(
      <FieldSelect aria-label="fs">
        <option value="a">Alpha</option>
        <option value="b">Beta</option>
        <option value="c">Gamma</option>
      </FieldSelect>,
    );
    const el = screen.getByLabelText("fs") as HTMLSelectElement;
    expect(el.options).toHaveLength(3);
    expect([...el.options].map((o) => o.value)).toEqual(["a", "b", "c"]);
    expect([...el.options].map((o) => o.text)).toEqual(["Alpha", "Beta", "Gamma"]);
  });

  it("forwards id, name, and required to the underlying <select>", () => {
    render(
      <FieldSelect id="my-fs" name="pilot" required aria-label="fs">
        <option value="a">A</option>
      </FieldSelect>,
    );
    const el = screen.getByLabelText("fs") as HTMLSelectElement;
    expect(el.id).toBe("my-fs");
    expect(el.name).toBe("pilot");
    expect(el.required).toBe(true);
  });

  it("preserves the selected value on controlled render", () => {
    render(
      <FieldSelect aria-label="fs" value="b" onChange={() => {}}>
        <option value="a">A</option>
        <option value="b">B</option>
        <option value="c">C</option>
      </FieldSelect>,
    );
    const el = screen.getByLabelText("fs") as HTMLSelectElement;
    expect(el.value).toBe("b");
  });

  it("invokes onChange when the selection changes", () => {
    // Uncontrolled — under a controlled value the JSDOM select reverts to
    // the prop before React fires change, so we assert the callback wiring
    // itself, not React's own reconciliation.
    const onChange = vi.fn();
    render(
      <FieldSelect aria-label="fs" defaultValue="a" onChange={onChange}>
        <option value="a">A</option>
        <option value="b">B</option>
      </FieldSelect>,
    );
    const el = screen.getByLabelText("fs") as HTMLSelectElement;
    fireEvent.change(el, { target: { value: "b" } });
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(el.value).toBe("b");
  });

  it("respects the disabled prop", () => {
    render(
      <FieldSelect aria-label="fs" disabled>
        <option value="a">A</option>
      </FieldSelect>,
    );
    const el = screen.getByLabelText("fs") as HTMLSelectElement;
    expect(el.disabled).toBe(true);
  });

  it("passes aria-invalid through unchanged", () => {
    render(
      <FieldSelect aria-label="fs" aria-invalid>
        <option value="a">A</option>
      </FieldSelect>,
    );
    const el = screen.getByLabelText("fs");
    expect(el.getAttribute("aria-invalid")).toBe("true");
  });

  it("merges the caller className with the built-in class list", () => {
    render(
      <FieldSelect aria-label="fs" className="w-40">
        <option value="a">A</option>
      </FieldSelect>,
    );
    const el = screen.getByLabelText("fs");
    // Class merger keeps both the built-in tokens and the caller's utility.
    expect(el.className).toContain("w-40");
    expect(el.className).toContain("border-input");
  });

  it("honours defaultValue for uncontrolled use", () => {
    render(
      <FieldSelect aria-label="fs" defaultValue="b">
        <option value="a">A</option>
        <option value="b">B</option>
      </FieldSelect>,
    );
    const el = screen.getByLabelText("fs") as HTMLSelectElement;
    expect(el.value).toBe("b");
  });
});
