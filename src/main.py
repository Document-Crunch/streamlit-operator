import kopf
import kubernetes
import os

from src.templating import template_deployment, template_service, template_ingress, template_secrets
import yaml
import logging


global config

@kopf.on.startup()
def configure(settings: kopf.OperatorSettings, **_):
    global config
    config = yaml.safe_load(open("/config/config.yaml"))
    logging.info(f"Loaded config: {config}")
    login = kubernetes.config.load_incluster_config()
    client = kubernetes.client.CustomObjectsApi()
    
    # Get the current namespace from the environment
    namespace = os.environ.get("NAMESPACE", "streamlit")
    
    try:
        client.create_namespaced_custom_object(
            group="document-crunch.com",
            version="v1",
            namespace=namespace,
            plural="streamlit-apps",
            body={
                "apiVersion": "document-crunch.com/v1",
                "kind": "StreamlitApp",
                "metadata": {
                    "name": "hub",
                    "namespace": namespace,
                },
                "spec": {
                    "repo": "https://github.com/document-crunch/streamlit-operator.git",
                    "branch": "main",
                    "code_dir": "streamlit-hub",
                    "has_secrets": False,
                },
            },
        )
        logging.info("Created hub StreamlitApp successfully")
    except kubernetes.client.exceptions.ApiException as e:
        if e.status == 409:
            # Resource already exists, this is fine
            logging.info("Hub StreamlitApp already exists, skipping creation")
        else:
            # Re-raise other API exceptions
            logging.error(f"Failed to create hub StreamlitApp: {e}")
            raise
    except Exception as e:
        logging.error(f"Failed to create custom object: {e}")


@kopf.on.create('streamlit-apps')
def create_fn(spec, name, namespace, logger, **kwargs):
    # Get the current namespace from the environment instead of hardcoding
    namespace = os.environ.get("NAMESPACE", "streamlit")
    logger.info(f"Using namespace: {namespace}")

    # Get params from spec
    repo = spec.get('repo', None)
    branch = spec.get('branch', None)
    code_dir = spec.get('code_dir', None)
    has_secrets = spec.get('has_secrets', False)

    if not repo:
        raise kopf.PermanentError(f"Repo must be set. Got {repo!r}.")
    if not branch:
        raise kopf.PermanentError(f"Branch must be set. Got {branch!r}.")
    if not code_dir:
        raise kopf.PermanentError(f"Code directory must be set. Got {code_dir!r}.")

    api = kubernetes.client.CoreV1Api()
    apps_api = kubernetes.client.AppsV1Api()
    networking_api = kubernetes.client.NetworkingV1Api()
    custom_api = kubernetes.client.CustomObjectsApi()

    # Template the deployment with the has_secrets flag
    deployment_data = template_deployment(name, repo, branch, code_dir, has_secrets)
    kopf.adopt(deployment_data)

    # Create the secrets if has_secrets is True
    if has_secrets:
        # Template the secrets
        secrets_data = template_secrets(name)
        kopf.adopt(secrets_data)
        try:
            # Create the secret resource
            custom_api.create_namespaced_custom_object(
                group="onepassword.com",
                version="v1",
                namespace=namespace,
                plural="onepassworditems",
                body=secrets_data,
            )
            logger.info(f"Created secrets for {name}")
        except kubernetes.client.exceptions.ApiException as e:
            if e.status == 409:
                # Secret already exists, this is fine
                logger.info(f"Secret for {name} already exists, skipping creation")
            else:
                # Re-raise other API exceptions
                logger.error(f"Failed to create secret for {name}: {e}")
                raise
        except Exception as e:
            logger.error(f"Failed to create secret: {e}")

    # Template the service
    service_data = template_service(name)
    kopf.adopt(service_data)

    # Template the ingress
    ingress_data = template_ingress(name, config["baseDnsRecord"], config["ingressAnnotations"], config["suffix"])
    kopf.adopt(ingress_data)

    # Create the deployment
    deployment_obj = apps_api.create_namespaced_deployment(
        namespace=namespace,
        body=deployment_data,
    )

    # Create the service
    service_obj = api.create_namespaced_service(
        namespace=namespace,
        body=service_data,
    )

    # Create the ingress
    ingress_obj = networking_api.create_namespaced_ingress(
        namespace=namespace,
        body=ingress_data,
    )

    return {
        'ingress-name': ingress_obj.metadata.name,
        'service-name': service_obj.metadata.name,
        'deployment-name': deployment_obj.metadata.name
    }
