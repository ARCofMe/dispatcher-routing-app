import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import StopList, { deriveEnd } from "./StopList";

describe("deriveEnd", () => {
  it("returns provided end when present", () => {
    expect(deriveEnd("08:00", "09:00")).toBe("09:00");
  });

  it("infers sensible defaults based on start", () => {
    expect(deriveEnd("06:30")).toBe("12:00");
    expect(deriveEnd("09:00")).toBe("16:00");
    expect(deriveEnd("12:15")).toBe("17:00");
  });

  it("falls back to em dash for missing values", () => {
    expect(deriveEnd()).toBe("—");
  });
});

describe("StopList", () => {
  const stops = [
    { id: "1", customer_name: "Alpha", address: "123 Main", window_start: "08:00", status: "scheduled" },
    { id: "2", customer_name: "Beta", address: "456 Oak", window_start: "09:00", status: "in-progress" },
  ];

  it("cycles status when status button clicked", async () => {
    const onStatusChange = vi.fn();
    render(<StopList stops={stops} onStatusChange={onStatusChange} />);
    const user = userEvent.setup();
    const statusBtn = screen.getByRole("button", { name: "scheduled" });
    await user.click(statusBtn);
    expect(onStatusChange).toHaveBeenCalledWith(0, "in-progress");
  });

  it("renders customer names and addresses", () => {
    render(<StopList stops={stops} />);
    expect(screen.getByText("1. Alpha")).toBeInTheDocument();
    expect(screen.getByText("2. Beta")).toBeInTheDocument();
    expect(screen.getByText("123 Main")).toBeInTheDocument();
    expect(screen.getByText("456 Oak")).toBeInTheDocument();
  });
});
