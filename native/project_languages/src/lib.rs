use pyo3::prelude::*;
use serde::Serialize;
use std::fs::{self, File};
use std::io::Read;
use std::path::{Path, PathBuf};
use tokei::{Config, Languages};

const TOKEI_VERSION: &str = "15.0.0";
const HEADER_LIMIT_BYTES: u64 = 128 * 1024;

#[derive(Serialize)]
struct NativeFileReport {
    path: String,
    language: String,
    bytes: u64,
    total_lines: usize,
    code_lines: usize,
    comment_lines: usize,
    blank_lines: usize,
    inaccurate: bool,
    excluded_reason: Option<&'static str>,
}

#[derive(Serialize)]
struct NativeScanPayload {
    engine: &'static str,
    engine_version: &'static str,
    files: Vec<NativeFileReport>,
    inaccurate_languages: Vec<String>,
}

fn looks_binary(path: &Path) -> bool {
    let mut file = match File::open(path) {
        Ok(file) => file,
        Err(_) => return false,
    };
    let mut sample = [0_u8; 8192];
    let read = match file.read(&mut sample) {
        Ok(read) => read,
        Err(_) => return false,
    };
    if read == 0 {
        return false;
    }
    let sample = &sample[..read];
    if sample.contains(&0) {
        return true;
    }
    let suspicious = sample
        .iter()
        .filter(|value| **value < 32 && !matches!(**value, 7 | 8 | 9 | 10 | 12 | 13 | 27))
        .count();
    suspicious * 10 >= sample.len()
}

fn generated_name(path: &Path) -> bool {
    let name = path
        .file_name()
        .and_then(|value| value.to_str())
        .unwrap_or_default()
        .to_ascii_lowercase();
    name.ends_with(".map")
        || name.ends_with(".min.css")
        || name.ends_with(".min.js")
        || name.ends_with(".min.mjs")
        || name.ends_with(".min.cjs")
}

fn generated_header(path: &Path) -> bool {
    let file = match File::open(path) {
        Ok(file) => file,
        Err(_) => return false,
    };
    let mut bytes = Vec::new();
    if file
        .take(HEADER_LIMIT_BYTES)
        .read_to_end(&mut bytes)
        .is_err()
    {
        return false;
    }
    let text = String::from_utf8_lossy(&bytes);
    let header = text
        .lines()
        .take(20)
        .collect::<Vec<_>>()
        .join("\n")
        .to_ascii_lowercase();
    header.contains("@generated")
        || header.contains("auto-generated")
        || header.contains("auto generated")
        || header.contains("automatically generated")
        || (header.contains("code generated") && header.contains("do not edit"))
        || header.lines().any(|line| {
            line.trim_end_matches(&['.', '!', ' ', '\t'][..])
                .ends_with("do not edit")
        })
}

fn exclusion_reason(path: &Path, size: u64, max_file_size_bytes: u64) -> Option<&'static str> {
    if size > max_file_size_bytes {
        return Some("oversized");
    }
    if looks_binary(path) {
        return Some("binary");
    }
    if generated_name(path) || generated_header(path) {
        return Some("generated");
    }
    None
}

fn absolute_path(path: &Path) -> PathBuf {
    if path.is_absolute() {
        return path.to_path_buf();
    }
    std::env::current_dir()
        .map(|current| current.join(path))
        .unwrap_or_else(|_| path.to_path_buf())
}

fn scan_config() -> Config {
    Config {
        hidden: Some(true),
        no_ignore: Some(false),
        no_ignore_parent: Some(false),
        no_ignore_dot: Some(false),
        no_ignore_vcs: Some(false),
        treat_doc_strings_as_comments: Some(false),
        ..Config::default()
    }
}

fn collect_languages(scan_paths: Vec<String>, excluded_directory_names: Vec<String>) -> Languages {
    let ignored_storage = excluded_directory_names;
    let ignored = ignored_storage
        .iter()
        .map(String::as_str)
        .collect::<Vec<_>>();
    let scan_paths = scan_paths
        .into_iter()
        .map(PathBuf::from)
        .collect::<Vec<_>>();
    let mut languages = Languages::new();
    languages.get_statistics(&scan_paths, &ignored, &scan_config());
    languages
}

fn serialize_payload(
    mut files: Vec<NativeFileReport>,
    mut inaccurate_languages: Vec<String>,
) -> PyResult<String> {
    files.sort_by(|left, right| left.path.cmp(&right.path));
    inaccurate_languages.sort();
    inaccurate_languages.dedup();
    serde_json::to_string(&NativeScanPayload {
        engine: "Tokei",
        engine_version: TOKEI_VERSION,
        files,
        inaccurate_languages,
    })
    .map_err(|error| pyo3::exceptions::PyRuntimeError::new_err(error.to_string()))
}

fn scan_paths_json_impl(
    scan_paths: Vec<String>,
    excluded_directory_names: Vec<String>,
    max_file_size_bytes: u64,
) -> PyResult<String> {
    let languages = collect_languages(scan_paths, excluded_directory_names);
    let mut files = Vec::new();
    let mut inaccurate_languages = Vec::new();
    for (language_type, language) in languages.iter() {
        let language_name = language_type.name().to_string();
        if language.inaccurate {
            inaccurate_languages.push(language_name.clone());
        }
        for report in &language.reports {
            let path = absolute_path(&report.name);
            let size = fs::metadata(&path)
                .map(|metadata| metadata.len())
                .unwrap_or(0);
            let stats = report.stats.summarise();
            files.push(NativeFileReport {
                path: path.to_string_lossy().into_owned(),
                language: language_name.clone(),
                bytes: size,
                total_lines: stats.lines(),
                code_lines: stats.code,
                comment_lines: stats.comments,
                blank_lines: stats.blanks,
                inaccurate: language.inaccurate,
                excluded_reason: exclusion_reason(&path, size, max_file_size_bytes),
            });
        }
    }
    serialize_payload(files, inaccurate_languages)
}

#[pyfunction]
fn scan_project_json(
    scan_path: String,
    excluded_directory_names: Vec<String>,
    max_file_size_bytes: u64,
) -> PyResult<String> {
    scan_paths_json_impl(
        vec![scan_path],
        excluded_directory_names,
        max_file_size_bytes,
    )
}

#[pyfunction]
fn scan_projects_json(
    scan_paths: Vec<String>,
    excluded_directory_names: Vec<String>,
    max_file_size_bytes: u64,
) -> PyResult<String> {
    scan_paths_json_impl(scan_paths, excluded_directory_names, max_file_size_bytes)
}

#[pymodule]
fn _project_languages_native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(scan_project_json, module)?)?;
    module.add_function(wrap_pyfunction!(scan_projects_json, module)?)?;
    Ok(())
}
