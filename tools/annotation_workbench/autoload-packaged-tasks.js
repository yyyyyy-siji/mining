const requestedSource = new URLSearchParams(globalThis.location.search).get("autoload");

if (requestedSource === "fixture-assisted") {
  try {
    const [developmentModule, calibrationModule] = await Promise.all([
      import("../../sample_data/p13_2/human_tasks/human_tasks_development.json", {
        with: { type: "json" },
      }),
      import("../../sample_data/p13_2/human_tasks/human_tasks_calibration.json", {
        with: { type: "json" },
      }),
    ]);
    globalThis.dispatchEvent(new CustomEvent("annotation-workbench:autoload", {
      detail: [developmentModule.default, calibrationModule.default],
    }));
  } catch (error) {
    globalThis.dispatchEvent(new CustomEvent("annotation-workbench:autoload-error", {
      detail: error instanceof Error ? error.message : String(error),
    }));
  }
}
