import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import {
  Client,
  StreamableHTTPClientTransport,
} from "@modelcontextprotocol/client";
import {
  McpServer,
  createMcpHandler,
  fromJsonSchema,
} from "@modelcontextprotocol/server";
import { z } from "zod";

const outputArgument = process.argv[2];
if (!outputArgument) {
  throw new Error("Usage: pnpm run evidence -- <output-directory>");
}

const exampleDirectory = dirname(fileURLToPath(import.meta.url));
const repositoryRoot = resolve(exampleDirectory, "../../..");
const schemaPath = resolve(
  repositoryRoot,
  "src/qzx/resources/schemas/result-contract-v1.schema.json",
);
const outputDirectory = resolve(outputArgument);
const contractSchema = JSON.parse(await readFile(schemaPath, "utf8"));

function buildServer() {
  const server = new McpServer({
    name: "qzx-result-contract-sdk-evidence",
    version: "1.0.0",
  });

  server.registerTool(
    "lookup_widget",
    {
      description:
        "Look up one synthetic widget for a QZX interoperability test.",
      inputSchema: z.object({ fail: z.boolean() }),
      outputSchema: fromJsonSchema(contractSchema),
    },
    async ({ fail }) => {
      const result = fail
        ? {
            success: false,
            message: "The requested widget was not found.",
            error_code: "widget_not_found",
            details: { widget_id: "missing-widget" },
          }
        : {
            success: true,
            message: "The requested widget was returned.",
            details: { widget_id: "widget-1", status: "ready" },
          };

      return {
        content: [{ type: "text", text: JSON.stringify(result) }],
        structuredContent: result,
        isError: fail,
      };
    },
  );
  return server;
}

async function parseWireDocuments(capture) {
  const body = await capture.response;
  if (capture.contentType.includes("application/json")) {
    return [JSON.parse(body)];
  }
  return body
    .split(/\r?\n\r?\n/)
    .map((event) =>
      event
        .split(/\r?\n/)
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice("data:".length).trimStart())
        .join("\n"),
    )
    .filter(Boolean)
    .map((data) => JSON.parse(data));
}

const handler = createMcpHandler(buildServer);
const wireCaptures = [];
const transport = new StreamableHTTPClientTransport(
  new URL("http://test.local/mcp"),
  {
    fetch: async (url, init) => {
      const request = new Request(url, init);
      const requestDocument =
        request.method === "POST" ? await request.clone().json() : null;
      const response = await handler.fetch(request);
      if (requestDocument?.method === "tools/call") {
        wireCaptures.push({
          request: requestDocument,
          response: response.clone().text(),
          contentType: response.headers.get("content-type") ?? "",
        });
      }
      return response;
    },
  },
);

const client = new Client(
  { name: "qzx-result-contract-sdk-evidence-client", version: "1.0.0" },
  { versionNegotiation: { mode: { pin: "2026-07-28" } } },
);

try {
  await client.connect(transport);
  if (client.getProtocolEra() !== "modern") {
    throw new Error(
      `Expected a modern MCP connection, got ${client.getProtocolEra()}.`,
    );
  }

  const listedTools = await client.listTools();
  const toolDefinition = listedTools.tools.find(
    (tool) => tool.name === "lookup_widget",
  );
  if (!toolDefinition) {
    throw new Error("The official MCP client did not discover lookup_widget.");
  }

  const success = await client.callTool({
    name: "lookup_widget",
    arguments: { fail: false },
  });
  const failure = await client.callTool({
    name: "lookup_widget",
    arguments: { fail: true },
  });
  if (
    success.isError === true ||
    success.structuredContent?.success !== true ||
    failure.isError !== true ||
    failure.structuredContent?.success !== false
  ) {
    throw new Error(
      "The official MCP client observed an inconsistent result pair.",
    );
  }

  const completedResults = new Map();
  for (const capture of wireCaptures) {
    const documents = await parseWireDocuments(capture);
    const response = documents.find(
      (document) => document.id === capture.request.id,
    );
    if (!response?.result) {
      throw new Error(
        `No JSON-RPC tool result was captured for request ${capture.request.id}.`,
      );
    }
    completedResults.set(
      Boolean(capture.request.params.arguments.fail),
      response.result,
    );
  }

  const rawSuccess = completedResults.get(false);
  const rawFailure = completedResults.get(true);
  if (
    rawSuccess?.resultType !== "complete" ||
    rawFailure?.resultType !== "complete"
  ) {
    throw new Error("The complete MCP 2026-07-28 wire pair was not captured.");
  }

  await mkdir(outputDirectory, { recursive: true });
  const evidenceMetadata = {
    success: true,
    message: "Official MCP TypeScript SDK v2 reference evidence generated.",
    details: {
      evidence_kind: "qzx_maintained_reference",
      independent_adoption: false,
      protocol: "2026-07-28",
      protocol_era: client.getProtocolEra(),
      transport: "in_process_streamable_http_fetch",
      packages: {
        "@modelcontextprotocol/client": "2.0.0",
        "@modelcontextprotocol/server": "2.0.0",
        zod: "4.4.3",
      },
      runtime: {
        node: process.version,
        platform: process.platform,
        architecture: process.arch,
      },
      output_directory: outputDirectory,
      files: [
        "tool-definition.json",
        "success.json",
        "failure.json",
        "evidence-metadata.json",
      ],
    },
  };
  for (const [filename, document] of [
    ["tool-definition.json", toolDefinition],
    ["success.json", rawSuccess],
    ["failure.json", rawFailure],
    ["evidence-metadata.json", evidenceMetadata],
  ]) {
    await writeFile(
      resolve(outputDirectory, filename),
      `${JSON.stringify(document, null, 2)}\n`,
      "utf8",
    );
  }

  process.stdout.write(`${JSON.stringify(evidenceMetadata, null, 2)}\n`);
} finally {
  await client.close();
  await handler.close();
}
