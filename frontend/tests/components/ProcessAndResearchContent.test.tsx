import { render, screen } from "@testing-library/react";
import ProcessAndResearchContent from "src/pages/content/ProcessAndResearchContent";

describe("Process Content", () => {
  it("Renders without errors", () => {
    render(<ProcessAndResearchContent />);
    const processH3 = screen.getByRole("heading", {
      level: 2,
      name: /The process/i,
    });
    const researchH3 = screen.getByRole("heading", {
      level: 2,
      name: /The research/i,
    });

    expect(processH3).toBeInTheDocument();
    expect(researchH3).toBeInTheDocument();
  });
});