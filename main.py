#!/usr/bin/env python3
# -*- coding:utf-8 -*-


import json
import logging
import os
from api4jenkins import Jenkins
from time import time, sleep


log_level = os.environ.get("INPUT_LOG_LEVEL", "INFO")
logging.basicConfig(format="JENKINS_ACTION: %(message)s", level=log_level)


def main():
    # jenkins info
    url = os.environ.get("INPUT_URL")
    job_name = os.environ["INPUT_JOB_NAME"]
    username = os.environ["INPUT_USERNAME"]
    api_token = os.environ["INPUT_API_TOKEN"]
    # parameters = os.environ.get("INPUT_PARAMETERS")

    # connection settings
    cookies = os.environ.get("INPUT_COOKIES")
    timeout = int(os.environ.get("INPUT_TIMEOUT"))
    start_timeout = int(os.environ.get("INPUT_START_TIMEOUT"))
    interval = int(os.environ.get("INPUT_INTERVAL"))

    # pull request info
    pr_num = os.environ.get("INPUT_PR_NUMBER")
    pr_head_sha = os.environ.get("INPUT_PR_HEAD_SHA")
    project_name = os.environ["INPUT_PROJECT_NAME"]
    project_revision = os.environ["INPUT_PROJECT_REVISION"]
    project_branch = os.environ["INPUT_PROJECT_BRANCH"]

    # node settings
    core_num = os.environ.get("INPUT_CORE_NUM")
    gpu_num = os.environ.get("INPUT_GPU_NUM")
    memory_size = os.environ.get("INPUT_MEMORY_SIZE")
    storage_size = os.environ.get("INPUT_STORAGE_SIZE")
    platform = os.environ["INPUT_PLATFORM"]
    docker_image = os.environ.get("INPUT_DOCKER_IMAGE")
    node_os = os.environ.get("INPUT_OS")

    # test job info
    job_config_file = os.environ["INPUT_JOB_CONFIG_FILE"]

    with open(job_config_file, "r") as f:
        job_config = f.read()

    if cookies:
        try:
            cookies = json.loads(cookies)
        except json.JSONDecodeError as e:
            raise Exception("`cookies` is not valid JSON.") from e
    else:
        cookies = {}

    jenkins = Jenkins(url, auth=(username, api_token), cookies=cookies)

    try:
        jenkins.version
    except Exception as e:
        raise Exception("Could not connect to Jenkins.") from e

    logging.info("Successfully connected to Jenkins.")

    configs = {
        "core_num": core_num,
        "gpu_num": gpu_num,
        "memory_size": memory_size,
        "storage_size": storage_size,
        "platform": platform,
        "docker_image": docker_image,
        "node_os": node_os,
        "project_name": project_name,
        "job_config": job_config,
    }

    entrance_queue_item = jenkins.build_job(job_name, **configs)
    logging.info("Start to create get test job")

    t0 = time()
    sleep(interval)
    while time() - t0 < start_timeout:
        entrance_build = entrance_queue_item.get_build()
        if entrance_build:
            break
        logging.info(f"Waiting for creating test job. Waiting {interval} seconds.")
        sleep(interval)
    else:
        raise Exception(
            f"Timeout to create test job. Waited for {start_timeout} seconds."
        )

    sleep(interval)
    while time() - t0 < start_timeout:
        entrance_result = entrance_build.result
        if entrance_result == "SUCCESS":
            test_job_name = entrance_build.description
            break
        elif entrance_result in ("FAILURE", "ABORTED", "UNSTABLE"):
            raise Exception(f"Failed to create test job. Build has failed ☹️.")
        logging.info(f"Waiting for creating test job. Waiting {interval} seconds.")
        sleep(interval)
    else:
        raise Exception(
            f"Timeout to create test job. Waited for {start_timeout} seconds."
        )

    node_tag = f"{project_name}-{entrance_build.number}"
    parameters = {
        "pr_num": pr_num,
        "pr_head_sha": pr_head_sha,
        "project_name": project_name,
        "project_revision": project_revision,
        "project_branch": project_branch,
        "node_tag": node_tag,
    }

    queue_item = jenkins.build_job(test_job_name, **parameters)
    logging.info(f"Requested to build {test_job_name}")

    t0 = time()
    sleep(interval)
    while time() - t0 < timeout:
        build = queue_item.get_build()
        if build:
            break
        logging.info(f"Test job not started yet. Waiting {interval} seconds.")
        sleep(interval)
    else:
        raise Exception(f"Timeout to start test job. Waited for {timeout} seconds.")

    sleep(interval)
    while time() - t0 < timeout:
        result = build.result
        if result == "SUCCESS":
            logging.info("Build successful 🎉")
            job_log_url = build.description
            with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
                print(f"log_url={job_log_url}", file=fh)
            print(f"::notice title=log_url::{job_log_url}")
            return
        elif result in ("FAILURE", "ABORTED", "UNSTABLE"):
            raise Exception(f'Build status returned "{result}". Build has failed ☹️.')
        logging.info(f"Build not finished yet. Waiting {interval} seconds.")
        sleep(interval)
    else:
        raise Exception(
            f"Build has not finished and timed out. Waited for {timeout} seconds."
        )


if __name__ == "__main__":
    main()
