import { mkdir, copyFile, readdir } from "node:fs/promises";
import { join } from "node:path";

// Only this allowlist is public: generated financial reports never enter Vercel.
await mkdir("dist/app/js", { recursive: true });
await copyFile("frontend/index.html", "dist/index.html");
await copyFile("frontend/shell.css", "dist/app/shell.css");
for (const file of await readdir("frontend/js")) {
  if (file.endsWith(".js"))
    await copyFile(join("frontend/js", file), join("dist/app/js", file));
}
console.log("Frontend publicado sem extratos, relatórios ou credenciais.");
