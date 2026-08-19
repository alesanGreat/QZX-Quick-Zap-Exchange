package qzx.evidence;

import io.modelcontextprotocol.client.McpClient;
import io.modelcontextprotocol.client.McpSyncClient;
import io.modelcontextprotocol.client.transport.ServerParameters;
import io.modelcontextprotocol.client.transport.StdioClientTransport;
import io.modelcontextprotocol.json.McpJsonDefaults;
import io.modelcontextprotocol.json.McpJsonMapper;
import io.modelcontextprotocol.json.TypeRef;
import io.modelcontextprotocol.server.McpServer;
import io.modelcontextprotocol.server.McpServerFeatures;
import io.modelcontextprotocol.server.McpSyncServer;
import io.modelcontextprotocol.server.transport.StdioServerTransportProvider;
import io.modelcontextprotocol.spec.McpSchema;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.time.Duration;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CountDownLatch;

public final class Main {

	private static final String PROTOCOL_VERSION = "2025-11-25";

	private static final String SDK_VERSION = "2.0.0";

	private static final String TOOL_NAME = "qzx_reference_lookup";

	private static final McpJsonMapper JSON = McpJsonDefaults.getMapper();

	private static final Map<String, String> EXPECTED_EVIDENCE_SHA256 = Map.of("tool-definition.json",
			"1207f0fcd064467801f5c7791d73a0d41266ec4158547abe595ef6e10b11f869", "success.json",
			"2b96692e5b4edbfa63fa687050ba697f9070b9d1c49f3e054473c6b2da6c03ed", "failure.json",
			"e224c9ebea46fbbf75d32194fbb4897dd65859b0ca4deb4cbcf2383dc3a9289a");

	private Main() {
	}

	public static void main(String[] args) throws Exception {
		if (args.length == 2 && "--server".equals(args[0])) {
			runServer(Path.of(args[1]));
			return;
		}
		if (args.length != 2) {
			throw new IllegalArgumentException("Usage: <canonical-schema-path> <evidence-directory>");
		}
		runClient(Path.of(args[0]), Path.of(args[1]));
	}

	private static void runServer(Path schemaPath) throws Exception {
		Map<String, Object> schema = readMap(schemaPath);
		StdioServerTransportProvider transport = new StdioServerTransportProvider(JSON);
		McpServerFeatures.SyncToolSpecification tool = McpServerFeatures.SyncToolSpecification.builder()
			.tool(McpSchema.Tool.builder(TOOL_NAME, inputSchema())
				.description("Return one synthetic QZX Result Contract reference result.")
				.outputSchema(schema)
				.annotations(McpSchema.ToolAnnotations.builder()
					.readOnlyHint(true)
					.destructiveHint(false)
					.idempotentHint(true)
					.openWorldHint(false)
					.build())
				.build())
			.callHandler((exchange, request) -> createResult(Boolean.TRUE.equals(request.arguments().get("fail"))))
			.build();

		McpSyncServer server = McpServer.sync(transport)
			.serverInfo("qzx-java-reference-server", "1.0.0")
			.capabilities(McpSchema.ServerCapabilities.builder().tools(false).build())
			.tools(tool)
			.build();
		try {
			new CountDownLatch(1).await();
		}
		finally {
			server.closeGracefully();
		}
	}

	private static void runClient(Path schemaPath, Path evidenceDirectory) throws Exception {
		Path absoluteEvidence = evidenceDirectory.toAbsolutePath().normalize();
		Files.createDirectories(absoluteEvidence);
		Map<String, Object> canonicalSchema = readMap(schemaPath);

		ServerParameters parameters = ServerParameters.builder(javaCommand())
			.args("-cp", System.getProperty("java.class.path"), Main.class.getName(), "--server",
					schemaPath.toAbsolutePath().normalize().toString())
			.build();
		StdioClientTransport transport = new StdioClientTransport(parameters, JSON);
		McpSyncClient client = McpClient.sync(transport)
			.clientInfo(McpSchema.Implementation.builder("qzx-java-reference-client", "1.0.0").build())
			.requestTimeout(Duration.ofSeconds(30))
			.build();

		try {
			McpSchema.InitializeResult initialized = client.initialize();
			if (!PROTOCOL_VERSION.equals(initialized.protocolVersion())) {
				throw new IllegalStateException(
						"Expected MCP " + PROTOCOL_VERSION + ", received " + initialized.protocolVersion());
			}

			McpSchema.Tool listedTool = client.listTools()
				.tools()
				.stream()
				.filter(tool -> TOOL_NAME.equals(tool.name()))
				.findFirst()
				.orElseThrow();
			if (!canonicalSchema.equals(listedTool.outputSchema())) {
				throw new IllegalStateException("The official SDK changed the canonical inline output schema.");
			}

			McpSchema.CallToolResult success = call(client, false);
			McpSchema.CallToolResult failure = call(client, true);
			assertResult(success, true);
			assertResult(failure, false);

			writeJson(absoluteEvidence.resolve("tool-definition.json"), listedTool);
			writeJson(absoluteEvidence.resolve("success.json"), success);
			writeJson(absoluteEvidence.resolve("failure.json"), failure);
			Map<String, String> evidenceSha256 = verifyEvidenceDigests(absoluteEvidence);

			Map<String, Object> metadata = new LinkedHashMap<>();
			metadata.put("evidence_kind", "qzx_maintained_reference");
			metadata.put("independent_adoption", false);
			metadata.put("sdk", "modelcontextprotocol/java-sdk");
			metadata.put("artifact", "io.modelcontextprotocol.sdk:mcp");
			metadata.put("artifact_version", SDK_VERSION);
			metadata.put("protocol_version", initialized.protocolVersion());
			metadata.put("runtime", System.getProperty("java.runtime.version"));
			metadata.put("operating_system", System.getProperty("os.name"));
			metadata.put("transport", "subprocess_stdio_newline_delimited_json_rpc");
			metadata.put("jsonrpc_framing_exercised", true);
			metadata.put("wire_capture_retained", false);
			metadata.put("http_exercised", false);
			metadata.put("sse_exercised", false);
			metadata.put("output_schema_mode", "canonical_inline");
			metadata.put("contract_evidence_sha256", evidenceSha256);
			metadata.put("tool", TOOL_NAME);
			writeJson(absoluteEvidence.resolve("evidence-metadata.json"), metadata);
		}
		finally {
			client.closeGracefully();
		}
	}

	private static McpSchema.CallToolResult call(McpSyncClient client, boolean fail) {
		return client.callTool(McpSchema.CallToolRequest.builder(TOOL_NAME).arguments(Map.of("fail", fail)).build());
	}

	private static McpSchema.CallToolResult createResult(boolean fail) {
		Map<String, Object> structured = new LinkedHashMap<>();
		structured.put("success", !fail);
		structured.put("message", fail ? "Synthetic lookup rejected the requested item."
				: "Synthetic lookup returned the requested item.");
		if (fail) {
			structured.put("error", "The synthetic item does not exist.");
			structured.put("error_code", "item_not_found");
		}
		Map<String, Object> details = new LinkedHashMap<>();
		details.put("item", fail ? "missing-item" : "example-item");
		if (!fail) {
			details.put("value", 42);
		}
		details.put("source", "java-sdk-v2.0.0");
		structured.put("details", details);

		try {
			return McpSchema.CallToolResult.builder()
				.textContent(List.of(JSON.writeValueAsString(structured)))
				.structuredContent(structured)
				.isError(fail)
				.build();
		}
		catch (Exception exception) {
			throw new IllegalStateException("Could not serialize QZX compatibility text.", exception);
		}
	}

	private static void assertResult(McpSchema.CallToolResult result, boolean expectedSuccess) throws Exception {
		if (!(result.structuredContent() instanceof Map<?, ?> structured)) {
			throw new IllegalStateException("The official SDK omitted structuredContent.");
		}
		if (!Boolean.valueOf(expectedSuccess).equals(structured.get("success"))
				|| !Boolean.valueOf(!expectedSuccess).equals(result.isError())) {
			throw new IllegalStateException("The official SDK observed an inconsistent result pair.");
		}
		McpSchema.TextContent text = result.content()
			.stream()
			.filter(McpSchema.TextContent.class::isInstance)
			.map(McpSchema.TextContent.class::cast)
			.findFirst()
			.orElseThrow();
		if (!structured.equals(JSON.readValue(text.text(), new TypeRef<Map<String, Object>>() {
		}))) {
			throw new IllegalStateException("The compatibility text does not match structuredContent.");
		}
	}

	private static Map<String, Object> inputSchema() {
		Map<String, Object> failProperty = new LinkedHashMap<>();
		failProperty.put("type", "boolean");
		Map<String, Object> properties = new LinkedHashMap<>();
		properties.put("fail", failProperty);
		Map<String, Object> schema = new LinkedHashMap<>();
		schema.put("type", "object");
		schema.put("properties", properties);
		schema.put("required", List.of("fail"));
		schema.put("additionalProperties", false);
		return schema;
	}

	private static Map<String, Object> readMap(Path path) throws Exception {
		return JSON.readValue(Files.readString(path.toAbsolutePath().normalize(), StandardCharsets.UTF_8),
				new TypeRef<Map<String, Object>>() {
				});
	}

	private static void writeJson(Path path, Object value) throws Exception {
		Files.writeString(path, JSON.writeValueAsString(value) + "\n", StandardCharsets.UTF_8);
	}

	private static Map<String, String> verifyEvidenceDigests(Path evidenceDirectory) throws Exception {
		Map<String, String> observed = new LinkedHashMap<>();
		for (String filename : List.of("tool-definition.json", "success.json", "failure.json")) {
			String expected = EXPECTED_EVIDENCE_SHA256.get(filename);
			String digest = sha256(evidenceDirectory.resolve(filename));
			if (!expected.equals(digest)) {
				throw new IllegalStateException(
						filename + " changed from expected SHA-256 " + expected + " to " + digest + ".");
			}
			observed.put(filename, digest);
		}
		return observed;
	}

	private static String sha256(Path path) throws Exception {
		MessageDigest digest = MessageDigest.getInstance("SHA-256");
		return HexFormat.of().formatHex(digest.digest(Files.readAllBytes(path)));
	}

	private static String javaCommand() {
		String executable = System.getProperty("os.name").toLowerCase().contains("win") ? "java.exe" : "java";
		return Path.of(System.getProperty("java.home"), "bin", executable).toString();
	}

}
