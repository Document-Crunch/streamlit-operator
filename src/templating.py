import os

import yaml


def template_secrets(name):
    secrets_dict = {
        "apiVersion": "onepassword.com/v1",
        "kind": "OnePasswordItem",
        "metadata": {
            "name": f"{name}-secrets",
            "namespace": "streamlit", 
            "labels": {
                "app": f"{name}"
            }
        },
        "spec": {
            "itemPath": f"vaults/Dev Secrets/items/{name}-streamlit",
            "secretName": f"{name}-secrets",
            "secretType": "kubernetes.io/Opaque"
        }
    }
    return secrets_dict


def template_deployment(name, repo, branch, code_dir, has_secrets=False):
    deployment_dict = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": f"{name}",
            "namespace": "streamlit",
            "labels": {
                "app": f"{name}"
            }
        },
        "spec": {
            "replicas": 1,
            "selector": {
                "matchLabels": {
                    "app": f"{name}"
                }
            },
            "template": {
                "metadata": {
                    "labels": {
                        "app": f"{name}"
                    }
                },
                "spec": {
                    "serviceAccountName": "streamlit-serviceaccount",
                    "containers": [
                        {
                            "name": "git-sync",
                            "image": "registry.k8s.io/git-sync/git-sync:v4.4.0",
                            "volumeMounts": [
                                {
                                    "name": "code",
                                    "mountPath": "/tmp/code"
                                }
                            ],
                            "env": [
                                {"name": "GITSYNC_REPO", "value": f"{repo}"},
                                {"name": "GIT_SYNC_BRANCH", "value": f"{branch}"},
                                {"name": "GITSYNC_ROOT", "value": "/tmp/code"},
                                {"name": "GIT_SYNC_DEST", "value": "repo"},
                                {"name": "GIT_KNOWN_HOSTS", "value": "false"},
                                {"name": "GIT_SYNC_WAIT", "value": "60"},
                                {"name": "GIT_SYNC_SSH", "value": "false"},
                                {"name": "GITSYNC_GITHUB_APP_APPLICATION_ID", 
                                 "valueFrom": {
                                     "secretKeyRef": {
                                         "name": "github-app-credentials",
                                         "key": "App-Id"
                                     }
                                 }},
                                {"name": "GITSYNC_GITHUB_APP_INSTALLATION_ID", 
                                 "valueFrom": {
                                     "secretKeyRef": {
                                         "name": "github-app-credentials",
                                            "key": "Installation-Id"
                                     }
                                 }},
                                {"name": "GITSYNC_GITHUB_APP_PRIVATE_KEY", 
                                 "valueFrom": {
                                     "secretKeyRef": {
                                         "name": "github-app-credentials",
                                         "key": "streamlit-operator.pem"
                                     }
                                 }}
                            ]
                        },
                        {
                            "name": "streamlit",
                            "image": "python:3.9-slim",
                            "env": [
                                {"name": "IN_HUB", "value": "True"},
                                {"name": "CODE_DIR", "value": f"repo/{code_dir}"},
                                {"name": "ENTRYPOINT", "value": "main.py"},  
                            ],
                            "command": ["/app/launch/launch.sh"],
                            "ports": [{"containerPort": 80}],
                            "volumeMounts": [
                                {"name": "code", "mountPath": "/app"},
                                {"name": "launch", "mountPath": "/app/launch"}
                            ]
                        }
                    ],
                    "volumes": [
                        {"name": "code", "emptyDir": {}},
                        {
                            "name": "launch",
                            "configMap": {
                                "name": "streamlit-launch-script",
                                "defaultMode": 0o500
                            }
                        }
                    ]
                }
            }
        }
    }
    
    # Add envFrom if has_secrets is True
    if has_secrets:
        deployment_dict["spec"]["template"]["spec"]["containers"][1]["envFrom"] = [
            {
                "secretRef": {
                    "name": f"{name}-secrets"
                }
            }
        ]
    
    return deployment_dict


def template_service(name):
    service_dict = {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": f"{name}",
            "namespace": "streamlit"
        },
        "spec": {
            "ports": [
                {
                    "port": 80,
                    "targetPort": 80,
                    "protocol": "TCP"
                }
            ],
            "type": "NodePort",
            "selector": {
                "app": f"{name}"
            }
        }
    }
    return service_dict


def template_ingress(name, base_dns_path, ingress_annotations, suffix):
    dns_name = f"{name}{suffix}.{base_dns_path}"
    ingress_annotations = ingress_annotations or {}
    ingress_dict = {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "Ingress",
        "metadata": {
            "name": f"{name}",
            "annotations": {
                "alb.ingress.kubernetes.io/scheme": "internal",
                "alb.ingress.kubernetes.io/target-type": "ip",
                "alb.ingress.kubernetes.io/listen-ports": '[{"HTTP": 80}, {"HTTPS":443}]',
                "alb.ingress.kubernetes.io/ssl-redirect": "443",
                "external-dns.alpha.kubernetes.io/hostname": dns_name,
                **ingress_annotations
            },
            "namespace": "streamlit"
        },
        "spec": {
            "ingressClassName": "alb",
            "rules": [
                {
                    "host": dns_name,
                    "http": {
                        "paths": [
                            {
                                "path": "/*",
                                "pathType": "ImplementationSpecific",
                                "backend": {
                                    "service": {
                                        "name": f"{name}",
                                        "port": {
                                            "number": 80
                                        }
                                    }
                                }
                            }
                        ]
                    }
                }
            ]
        }
    }
    return ingress_dict
