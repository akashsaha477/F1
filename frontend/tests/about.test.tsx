import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import AboutPage, { SOCIALS } from "../src/pages/About";
import { renderPage } from "./helpers";

describe("About", () => {
  it("links to the code and every social profile in a new tab", () => {
    renderPage(<AboutPage />, "/about");
    const repo = screen.getByRole("link", { name: /View the code on GitHub/ });
    expect(repo).toHaveAttribute("href", "https://github.com/akashsaha477/F1");
    expect(repo).toHaveAttribute("target", "_blank");
    expect(SOCIALS.map((s) => s.name)).toEqual(["GitHub", "LinkedIn", "X", "Instagram", "Facebook"]);
    const links = screen.getAllByRole("link");
    for (const s of SOCIALS) {
      const link = links.find((a) => a.getAttribute("href") === s.url);
      expect(link, s.name).toBeDefined();
      expect(link).toHaveTextContent(s.handle);
      expect(link).toHaveAttribute("target", "_blank");
      expect(link).toHaveAttribute("rel", "noreferrer");
    }
  });
});
