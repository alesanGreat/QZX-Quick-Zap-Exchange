package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"runtime"
	"runtime/debug"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

const (
	protocolVersion = "2025-11-25"
	toolName        = "lookup_widget"
)

type lookupInput struct {
	Fail bool `json:"fail"`
}

type widgetDetails struct {
	WidgetID string `json:"widget_id"`
	Status   string `json:"status,omitempty"`
}

type resultDocument struct {
	Success   bool          `json:"success"`
	Message   string        `json:"message"`
	ErrorCode string        `json:"error_code,omitempty"`
	Details   widgetDetails `json:"details"`
}

func contractSchemaPath() (string, error) {
	_, source, _, ok := runtime.Caller(0)
	if !ok {
		return "", errors.New("could not locate the Go evidence source")
	}
	return filepath.Clean(filepath.Join(
		filepath.Dir(source),
		"..", "..", "..", "src", "qzx", "resources", "schemas",
		"result-contract-v1.schema.json",
	)), nil
}

func moduleVersion(modulePath string) string {
	info, ok := debug.ReadBuildInfo()
	if !ok {
		return "unavailable"
	}
	for _, dependency := range info.Deps {
		if dependency.Path == modulePath {
			if dependency.Replace != nil {
				return dependency.Replace.Version
			}
			return dependency.Version
		}
	}
	return "unavailable"
}

func writeJSON(path string, document any) error {
	encoded, err := json.MarshalIndent(document, "", "  ")
	if err != nil {
		return err
	}
	encoded = append(encoded, '\n')
	return os.WriteFile(path, encoded, 0o644)
}

func structuredSuccess(result *mcp.CallToolResult) (bool, bool) {
	document, ok := result.StructuredContent.(map[string]any)
	if !ok {
		return false, false
	}
	value, ok := document["success"].(bool)
	return value, ok
}

func loadContractSchema() ([]byte, map[string]any, error) {
	schemaPath, err := contractSchemaPath()
	if err != nil {
		return nil, nil, err
	}
	schemaBytes, err := os.ReadFile(schemaPath)
	if err != nil {
		return nil, nil, fmt.Errorf("read QZX contract schema: %w", err)
	}
	var contractSchema map[string]any
	if err := json.Unmarshal(schemaBytes, &contractSchema); err != nil {
		return nil, nil, fmt.Errorf("parse QZX contract schema: %w", err)
	}
	return schemaBytes, contractSchema, nil
}

func newEvidenceServer(schemaBytes []byte) *mcp.Server {
	server := mcp.NewServer(
		&mcp.Implementation{Name: "qzx-result-contract-go-sdk-evidence", Version: "1.0.0"},
		nil,
	)
	mcp.AddTool(server, &mcp.Tool{
		Name:         toolName,
		Description:  "Look up one synthetic widget for a QZX interoperability test.",
		OutputSchema: json.RawMessage(schemaBytes),
	}, func(_ context.Context, _ *mcp.CallToolRequest, input lookupInput) (*mcp.CallToolResult, resultDocument, error) {
		if input.Fail {
			return &mcp.CallToolResult{IsError: true}, resultDocument{
				Success:   false,
				Message:   "The requested widget was not found.",
				ErrorCode: "widget_not_found",
				Details:   widgetDetails{WidgetID: "missing-widget"},
			}, nil
		}
		return &mcp.CallToolResult{}, resultDocument{
			Success: true,
			Message: "The requested widget was returned.",
			Details: widgetDetails{WidgetID: "widget-1", Status: "ready"},
		}, nil
	})
	return server
}

func connectEvidenceClient(ctx context.Context, server *mcp.Server) (*mcp.ClientSession, func(), error) {
	clientTransport, serverTransport := mcp.NewInMemoryTransports()
	serverSession, err := server.Connect(ctx, serverTransport, nil)
	if err != nil {
		return nil, nil, fmt.Errorf("connect official MCP server: %w", err)
	}
	client := mcp.NewClient(
		&mcp.Implementation{Name: "qzx-result-contract-go-sdk-client", Version: "1.0.0"},
		nil,
	)
	clientSession, err := client.Connect(ctx, clientTransport, nil)
	if err != nil {
		_ = serverSession.Close()
		return nil, nil, fmt.Errorf("connect official MCP client: %w", err)
	}
	cleanup := func() {
		_ = clientSession.Close()
		_ = serverSession.Close()
	}
	return clientSession, cleanup, nil
}

func verifyProtocol(clientSession *mcp.ClientSession) error {
	if got := clientSession.InitializeResult().ProtocolVersion; got != protocolVersion {
		return fmt.Errorf("expected MCP %s, got %s", protocolVersion, got)
	}
	return nil
}

func discoverToolDefinition(ctx context.Context, clientSession *mcp.ClientSession, contractSchema map[string]any) (*mcp.Tool, error) {
	listedTools, err := clientSession.ListTools(ctx, nil)
	if err != nil {
		return nil, fmt.Errorf("list official MCP tools: %w", err)
	}
	for _, tool := range listedTools.Tools {
		if tool.Name != toolName {
			continue
		}
		if !reflect.DeepEqual(tool.OutputSchema, contractSchema) {
			return nil, errors.New("the official SDK changed the canonical inline output schema")
		}
		return tool, nil
	}
	return nil, errors.New("the official MCP client did not discover lookup_widget")
}

func callEvidenceCases(ctx context.Context, clientSession *mcp.ClientSession) (*mcp.CallToolResult, *mcp.CallToolResult, error) {
	success, err := clientSession.CallTool(ctx, &mcp.CallToolParams{
		Name:      toolName,
		Arguments: map[string]any{"fail": false},
	})
	if err != nil {
		return nil, nil, fmt.Errorf("call success case: %w", err)
	}
	failure, err := clientSession.CallTool(ctx, &mcp.CallToolParams{
		Name:      toolName,
		Arguments: map[string]any{"fail": true},
	})
	if err != nil {
		return nil, nil, fmt.Errorf("call failure case: %w", err)
	}
	return success, failure, nil
}

func verifyEvidenceCases(success, failure *mcp.CallToolResult) error {
	if value, ok := structuredSuccess(success); !ok || !value || success.IsError {
		return errors.New("the official MCP client observed an inconsistent success result")
	}
	if value, ok := structuredSuccess(failure); !ok || value || !failure.IsError {
		return errors.New("the official MCP client observed an inconsistent failure result")
	}
	return nil
}

func prepareOutputDirectory(outputDirectory string) (string, error) {
	absOutput, err := filepath.Abs(outputDirectory)
	if err != nil {
		return "", fmt.Errorf("resolve output directory: %w", err)
	}
	if err := os.MkdirAll(absOutput, 0o755); err != nil {
		return "", fmt.Errorf("create output directory: %w", err)
	}
	return absOutput, nil
}

func evidenceMetadata(absOutput string) map[string]any {
	return map[string]any{
		"evidence_kind":             "qzx_maintained_reference",
		"independent_adoption":      false,
		"protocol":                  protocolVersion,
		"protocol_era":              "legacy_initialize",
		"transport":                 "in_process_newline_delimited_json",
		"jsonrpc_framing_exercised": true,
		"wire_capture_retained":     false,
		"serialization":             "encoding_json_of_official_sdk_models",
		"packages": map[string]any{
			"github.com/modelcontextprotocol/go-sdk": moduleVersion("github.com/modelcontextprotocol/go-sdk"),
		},
		"runtime": map[string]any{
			"go":           runtime.Version(),
			"platform":     runtime.GOOS,
			"architecture": runtime.GOARCH,
		},
		"output_directory": absOutput,
		"files": []string{
			"tool-definition.json",
			"success.json",
			"failure.json",
			"evidence-metadata.json",
		},
	}
}

func writeEvidenceFiles(absOutput string, toolDefinition *mcp.Tool, success, failure *mcp.CallToolResult, metadata map[string]any) error {
	for name, document := range map[string]any{
		"tool-definition.json":   toolDefinition,
		"success.json":           success,
		"failure.json":           failure,
		"evidence-metadata.json": metadata,
	} {
		if err := writeJSON(filepath.Join(absOutput, name), document); err != nil {
			return fmt.Errorf("write %s: %w", name, err)
		}
	}
	return nil
}

func run(outputDirectory string) (map[string]any, error) {
	schemaBytes, contractSchema, err := loadContractSchema()
	if err != nil {
		return nil, err
	}
	server := newEvidenceServer(schemaBytes)
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	clientSession, cleanup, err := connectEvidenceClient(ctx, server)
	if err != nil {
		return nil, err
	}
	defer cleanup()
	if err := verifyProtocol(clientSession); err != nil {
		return nil, err
	}
	toolDefinition, err := discoverToolDefinition(ctx, clientSession, contractSchema)
	if err != nil {
		return nil, err
	}
	success, failure, err := callEvidenceCases(ctx, clientSession)
	if err != nil {
		return nil, err
	}
	if err := verifyEvidenceCases(success, failure); err != nil {
		return nil, err
	}
	absOutput, err := prepareOutputDirectory(outputDirectory)
	if err != nil {
		return nil, err
	}
	metadata := evidenceMetadata(absOutput)
	if err := writeEvidenceFiles(absOutput, toolDefinition, success, failure, metadata); err != nil {
		return nil, err
	}
	return metadata, nil
}

func main() {
	if len(os.Args) != 2 {
		fmt.Fprintln(os.Stderr, "Usage: go run . <output-directory>")
		os.Exit(2)
	}
	metadata, err := run(os.Args[1])
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	result := map[string]any{
		"success": true,
		"message": "Official MCP Go SDK v1.6.1 reference evidence generated.",
		"details": metadata,
	}
	encoder := json.NewEncoder(os.Stdout)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(result); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
