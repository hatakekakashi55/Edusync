"""
EduSync Backend - Compiler Service
Auto-extracted from main.py
"""
import logging
import os
import json
import asyncio
import uuid
import hashlib
import subprocess
import tempfile
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from bson import ObjectId
from pathlib import Path
import shutil
from concurrent.futures import ThreadPoolExecutor

from app.database import *
from app.config import *
from app.services.ai_wrapper import gemini_model, get_gemini_model, AIModelWrapper

logger = logging.getLogger("edusync")
executor = ThreadPoolExecutor(max_workers=10)

# Local command mapping for fallback (no Docker)
LOCAL_CMD_MAP = {
    "python": {"cmd": ["python"], "file_ext": "py"},
    "javascript": {"cmd": ["node"], "file_ext": "js"},
    "java": {"compile": ["javac"], "run": ["java", "Main"], "file_ext": "java", "src_name": "Main.java"},
    "c": {"compile": ["gcc", "-o"], "run": [], "file_ext": "c"},
    "cpp": {"compile": ["g++", "-o"], "run": [], "file_ext": "cpp"},
    "go": {"cmd": ["go", "run"], "file_ext": "go"},
    "rust": {"compile": ["rustc", "-o"], "run": [], "file_ext": "rs"},
}

class CompilerService:
    
    _docker_available = None  # Cache Docker availability check
    
    @staticmethod
    def sh_escape(s: str) -> str:
        """Escape string for shell command"""
        if s == "":
            return "''"
        return "'" + s.replace("'", "'\"'\"'") + "'"
    
    @staticmethod
    def is_docker_available() -> bool:
        """Check if Docker daemon is running. Result is cached."""
        if CompilerService._docker_available is not None:
            return CompilerService._docker_available
        try:
            result = subprocess.run(
                ["docker", "info"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5
            )
            CompilerService._docker_available = (result.returncode == 0)
        except Exception:
            CompilerService._docker_available = False
        
        if not CompilerService._docker_available:
            logger.warning("⚠️ Docker is NOT available. Using local execution fallback.")
        else:
            logger.info("✅ Docker is available.")
        return CompilerService._docker_available
    
    @staticmethod
    async def local_exec(cmd_list: list, workdir: Path, timeout: int, input_data: str = None):
        """Execute code locally via subprocess (fallback when Docker is unavailable)"""
        _executor = executor or ThreadPoolExecutor(max_workers=10)
        loop = asyncio.get_event_loop()
        
        def _run():
            try:
                input_bytes = input_data.encode('utf-8') if input_data else None
                result = subprocess.run(
                    cmd_list,
                    input=input_bytes,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=timeout,
                    cwd=str(workdir)
                )
                stdout = result.stdout.decode('utf-8', errors='replace') if result.stdout else ""
                stderr = result.stderr.decode('utf-8', errors='replace') if result.stderr else ""
                return result.returncode, stdout, stderr
            except subprocess.TimeoutExpired:
                return -1, "", f"❌ Time limit exceeded ({timeout}s)"
            except FileNotFoundError as e:
                return -1, "", f"❌ Command not found: {e}. Make sure the language runtime is installed locally."
            except Exception as e:
                return -1, "", f"❌ Local execution error: {str(e)}"
        
        return await loop.run_in_executor(_executor, _run)
    
    @staticmethod
    def run_subprocess(cmd_list, timeout, input_data=None):
        """Run subprocess synchronously"""
        try:
            input_text = input_data.encode() if input_data else None
            proc = subprocess.run(
                cmd_list,
                input=input_text,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,
                timeout=timeout
            )
            return proc.returncode, proc.stdout.decode('utf-8', errors='replace'), proc.stderr.decode('utf-8', errors='replace')
        except subprocess.TimeoutExpired as e:
            return -1, e.stdout.decode('utf-8', errors='replace') if e.stdout else "", (e.stderr.decode('utf-8', errors='replace') if e.stderr else "") + f"\nTimeout after {timeout}s"
        except Exception as e:
            return -1, "", str(e)
    
    @staticmethod
    async def docker_exec(image: str, workdir: Path, inner_cmd: str, timeout: int, input_data: str = None):
        """Secure docker run with writable /tmp"""
        container_cmd = [
            "docker", "run", "--rm", "-i",
            "--network", "none",
            "--cpus", DOCKER_CPU,
            "--memory", DOCKER_MEMORY,
            "--pids-limit", "64",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "-v", f"{str(workdir)}:/app:rw",
            "-w", "/app",
            image,
            "sh", "-c", inner_cmd
        ]
        
        _executor = executor or ThreadPoolExecutor(max_workers=10)
        loop = asyncio.get_event_loop()
        
        def run_subprocess_sync():
            try:
                input_bytes = input_data.encode('utf-8') if input_data else None
                result = subprocess.run(
                    container_cmd,
                    input=input_bytes,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=timeout
                )
                stdout = result.stdout.decode('utf-8', errors='replace') if result.stdout else ""
                stderr = result.stderr.decode('utf-8', errors='replace') if result.stderr else ""
                return result.returncode, stdout, stderr
            except subprocess.TimeoutExpired:
                return -1, "", f"❌ Time limit exceeded ({timeout}s)"
            except Exception as e:
                return -1, "", f"❌ Docker execution error: {str(e)}"
        
        try:
            return await loop.run_in_executor(_executor, run_subprocess_sync)
        except Exception as e:
            logger.error(f"Docker exec error: {e}")
            return -1, "", f"❌ Docker execution failed: {str(e)}"

    
    @staticmethod
    async def execute_code_safely(code: str, language: str, input_data: str = "", test_cases: List = None) -> Dict:
        """Execute code safely — uses Docker if available, otherwise falls back to local execution"""
        # Normalize language input
        language = language.lower().strip()
        
        # Language mapping for common aliases
        language_map = {
            "py": "python",
            "python3": "python",
            "js": "javascript",
            "node": "javascript",
            "nodejs": "javascript",
            "java8": "java",
            "java11": "java",
            "java17": "java",
            "c++": "cpp",
            "cplusplus": "cpp",
            "golang": "go",
            "rs": "rust"
        }
        
        # Map alias to standard language
        if language in language_map:
            language = language_map[language]
        
        # Debug logging
        logger.info(f"Executing code in language: {language}")
        
        # Check if language is supported
        if language not in LANG_CONFIG:
            logger.error(f"Language '{language}' not supported. Available: {list(LANG_CONFIG.keys())}")
            return {
                "success": False,
                "output": "",
                "error": f"❌ Language '{language}' not supported. Available languages: {', '.join(LANG_CONFIG.keys())}",
                "return_code": -1,
                "execution_time": 0,
                "memory_used": 0,
                "test_results": None
            }
        
        cfg = LANG_CONFIG[language]
        use_docker = CompilerService.is_docker_available()
        
        ext = cfg["file_ext"]
        tmpdir = Path(tempfile.mkdtemp(prefix=f"compiler-{language}-"))
        
        try:
            start_time = datetime.now()
            
            # Write source file
            if language == "java":
                src_name = f"Main.{ext}"
            else:
                src_name = f"main.{ext}"
            
            src_path = tmpdir / src_name
            src_path.write_text(code, encoding="utf-8")
            
            compile_stderr = None
            compile_time = 0
            
            # === EXECUTION ===
            if use_docker:
                # --- Docker mode ---
                if cfg.get("compile_cmd"):
                    compile_start = datetime.now()
                    compile_cmd = cfg["compile_cmd"].format(filename=src_name)
                    logger.info(f"[Docker] Compiling: {compile_cmd}")
                    exit_code, out, err = await CompilerService.docker_exec(
                        cfg["image"], tmpdir, compile_cmd, TIMEOUT_SECONDS
                    )
                    compile_time = (datetime.now() - compile_start).total_seconds()
                    compile_stderr = err
                    if exit_code != 0:
                        return {
                            "success": False, "output": out, "error": err,
                            "compile_error": compile_stderr, "return_code": exit_code,
                            "execution_time": compile_time, "memory_used": 0, "test_results": None
                        }
                
                run_cmd = cfg["run_cmd"].format(filename=src_name)
                logger.info(f"[Docker] Running: {run_cmd}")
                exit_code, stdout, stderr = await CompilerService.docker_exec(
                    cfg["image"], tmpdir, run_cmd, TIMEOUT_SECONDS, input_data
                )
            else:
                # --- Local fallback mode ---
                logger.info(f"[Local] Executing {language} code locally")
                local_cfg = LOCAL_CMD_MAP.get(language)
                
                if not local_cfg:
                    return {
                        "success": False, "output": "",
                        "error": f"❌ Local execution not supported for '{language}'. Please start Docker Desktop.",
                        "return_code": -1, "execution_time": 0, "memory_used": 0, "test_results": None
                    }
                
                # Compiled languages (C, C++, Java, Rust)
                if "compile" in local_cfg:
                    compile_start = datetime.now()
                    if language == "java":
                        compile_cmd_list = local_cfg["compile"] + [str(src_path)]
                    elif language in ("c", "cpp", "rust"):
                        out_path = str(tmpdir / "main_out")
                        compile_cmd_list = local_cfg["compile"] + [out_path, str(src_path)]
                    else:
                        compile_cmd_list = local_cfg["compile"] + [str(src_path)]
                    
                    logger.info(f"[Local] Compiling: {' '.join(compile_cmd_list)}")
                    exit_code, out, err = await CompilerService.local_exec(
                        compile_cmd_list, tmpdir, TIMEOUT_SECONDS
                    )
                    compile_time = (datetime.now() - compile_start).total_seconds()
                    compile_stderr = err
                    if exit_code != 0:
                        return {
                            "success": False, "output": out, "error": err,
                            "compile_error": compile_stderr, "return_code": exit_code,
                            "execution_time": compile_time, "memory_used": 0, "test_results": None
                        }
                    
                    # Run the compiled binary
                    if language == "java":
                        run_cmd_list = local_cfg["run"]
                    else:
                        run_cmd_list = [str(tmpdir / "main_out")]
                    
                    exit_code, stdout, stderr = await CompilerService.local_exec(
                        run_cmd_list, tmpdir, TIMEOUT_SECONDS, input_data
                    )
                else:
                    # Interpreted languages (Python, JS, Go)
                    run_cmd_list = local_cfg["cmd"] + [str(src_path)]
                    logger.info(f"[Local] Running: {' '.join(run_cmd_list)}")
                    exit_code, stdout, stderr = await CompilerService.local_exec(
                        run_cmd_list, tmpdir, TIMEOUT_SECONDS, input_data
                    )
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Run test cases if provided
            test_results = []
            if test_cases and isinstance(test_cases, list):
                logger.info(f"Running {len(test_cases)} test cases")
                for i, test_case in enumerate(test_cases):
                    test_input = test_case.get("input", "")
                    expected_output = test_case.get("output", "")
                    
                    if use_docker:
                        run_cmd = cfg["run_cmd"].format(filename=src_name)
                        test_exit_code, test_stdout, test_stderr = await CompilerService.docker_exec(
                            cfg["image"], tmpdir, run_cmd, TIMEOUT_SECONDS, test_input
                        )
                    else:
                        local_cfg = LOCAL_CMD_MAP.get(language, {})
                        if "compile" in local_cfg:
                            if language == "java":
                                test_cmd = local_cfg["run"]
                            else:
                                test_cmd = [str(tmpdir / "main_out")]
                        else:
                            test_cmd = local_cfg.get("cmd", ["python"]) + [str(src_path)]
                        test_exit_code, test_stdout, test_stderr = await CompilerService.local_exec(
                            test_cmd, tmpdir, TIMEOUT_SECONDS, test_input
                        )
                    
                    actual_output = test_stdout.strip() if test_stdout else ""
                    expected_output_clean = str(expected_output).strip() if expected_output else ""
                    
                    passed = (test_exit_code == 0 and actual_output == expected_output_clean)
                    
                    test_results.append({
                        "test_case": i + 1,
                        "input": test_input,
                        "expected_output": expected_output_clean,
                        "actual_output": actual_output,
                        "passed": passed,
                        "error": test_stderr if test_stderr else "",
                        "exit_code": test_exit_code
                    })
            
            # Check for common errors in stderr
            if stderr and "EOFError: EOF when reading a line" in stderr:
                stderr += "\n\n💡 Tip: Your code appears to use input(). Since this is a non-interactive compiler, you MUST provide the input values in the 'Custom Input' box before running the code."

            # Format success response
            mode = "docker" if use_docker else "local"
            result = {
                "success": exit_code == 0,
                "output": stdout,
                "error": stderr,
                "compile_error": compile_stderr if compile_stderr else "",
                "return_code": exit_code,
                "execution_time": round(execution_time, 4),
                "memory_used": 0,
                "test_results": test_results if test_cases else None,
                "compile_time": round(compile_time, 4) if cfg.get("compile_cmd") else 0,
                "language": language,
                "file_name": src_name,
                "execution_mode": mode
            }
            
            logger.info(f"[{mode.upper()}] Execution completed for {language}. Success: {exit_code == 0}, Time: {execution_time:.3f}s")
            return result
            
        except Exception as e:
            logger.error(f"Compiler error for {language}: {e}", exc_info=True)
            return {
                "success": False,
                "output": "",
                "error": f"❌ Unexpected error during execution: {str(e)}",
                "return_code": -1,
                "execution_time": 0,
                "memory_used": 0,
                "test_results": None
            }
        finally:
            # Cleanup temporary directory
            try:
                if os.path.exists(tmpdir):
                    shutil.rmtree(tmpdir, ignore_errors=True)
                    logger.debug(f"Cleaned up temp directory: {tmpdir}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp directory {tmpdir}: {e}")
    
    @staticmethod
    async def execute_simple_code(code: str, language: str = "python", timeout: int = 10) -> Dict:
        """Simplified version for quick code execution"""
        try:
            # Basic code validation
            if not code or len(code.strip()) == 0:
                return {
                    "success": False,
                    "output": "",
                    "error": "❌ Empty code provided",
                    "return_code": -1
                }
            
            # Limit code size
            if len(code) > 10000:
                return {
                    "success": False,
                    "output": "",
                    "error": "❌ Code too large (max 10KB)",
                    "return_code": -1
                }
            
            # Execute code
            result = await CompilerService.execute_code_safely(
                code=code,
                language=language,
                input_data="",
                test_cases=None
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Simple code execution error: {e}")
            return {
                "success": False,
                "output": "",
                "error": f"❌ Execution error: {str(e)}",
                "return_code": -1
            }
    
    @staticmethod
    async def validate_code(code: str, language: str, requirements: List[str] = None) -> Dict:
        """Validate code against requirements"""
        try:
            # Execute the code first
            exec_result = await CompilerService.execute_code_safely(code, language)
            
            # Basic validation
            validation_result = {
                "execution_success": exec_result["success"],
                "execution_output": exec_result["output"],
                "execution_error": exec_result["error"],
                "compile_error": exec_result.get("compile_error"),
                "execution_time": exec_result["execution_time"],
                "requirements_met": [],
                "requirements_failed": [],
                "suggestions": []
            }
            
            # Check requirements if provided
            if requirements and isinstance(requirements, list):
                for req in requirements:
                    if "import" in req.lower() and "import" in code:
                        validation_result["requirements_met"].append(req)
                    elif "function" in req.lower():
                        # Simple function check
                        if "def " in code:
                            validation_result["requirements_met"].append(req)
                        else:
                            validation_result["requirements_failed"].append(req)
                    else:
                        # Generic check - if requirement text appears in code
                        if req.lower() in code.lower():
                            validation_result["requirements_met"].append(req)
                        else:
                            validation_result["requirements_failed"].append(req)
            
            # Add suggestions based on errors
            if exec_result["error"]:
                if "syntax" in exec_result["error"].lower():
                    validation_result["suggestions"].append("Check for syntax errors")
                if "import" in exec_result["error"].lower():
                    validation_result["suggestions"].append("Check module imports")
                if "undefined" in exec_result["error"].lower():
                    validation_result["suggestions"].append("Check variable/function names")
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Code validation error: {e}")
            return {
                "execution_success": False,
                "execution_error": f"Validation error: {str(e)}",
                "requirements_met": [],
                "requirements_failed": requirements or [],
                "suggestions": ["Try testing your code with simple inputs first"]
            }
    
    @staticmethod
    async def benchmark_code(code: str, language: str, iterations: int = 5) -> Dict:
        """Benchmark code execution time"""
        try:
            if iterations < 1 or iterations > 20:
                iterations = 5
            
            execution_times = []
            outputs = []
            
            for i in range(iterations):
                start_time = datetime.now()
                result = await CompilerService.execute_code_safely(code, language)
                end_time = datetime.now()
                
                execution_time = (end_time - start_time).total_seconds()
                execution_times.append(execution_time)
                
                if i == 0:  # Only store output from first run
                    outputs.append(result["output"][:500])  # Limit output size
            
            # Calculate statistics
            avg_time = sum(execution_times) / len(execution_times)
            min_time = min(execution_times)
            max_time = max(execution_times)
            
            return {
                "iterations": iterations,
                "average_time": round(avg_time, 4),
                "min_time": round(min_time, 4),
                "max_time": round(max_time, 4),
                "execution_times": [round(t, 4) for t in execution_times],
                "sample_output": outputs[0] if outputs else "",
                "performance_rating": "fast" if avg_time < 1 else "moderate" if avg_time < 5 else "slow"
            }
            
        except Exception as e:
            logger.error(f"Benchmark error: {e}")
            return {
                "error": f"Benchmark failed: {str(e)}",
                "iterations": 0,
                "average_time": 0
            }
            
