import base from "@aranlucas/oxforge/format-tailwind";

const config = {
  ...base,
  sortTailwindcss: {
    ...base.sortTailwindcss,
    functions: [...base.sortTailwindcss.functions, "cx"],
    stylesheet: "./src/styles.css",
  },
};

export default config;
