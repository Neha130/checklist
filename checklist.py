import subprocess 
import json
import os  # Import the os module to access environment variables

def get_kubectl_output(command):
    """Execute kubectl command and return JSON output."""
    try:
        output = subprocess.check_output(command).decode("utf-8")
        return json.loads(output)
    except subprocess.CalledProcessError as e:
        print(f"Command '{' '.join(command)}' failed with error: {str(e)}")
        return None

def get_service_monitors(namespace):
    """Fetch all ServiceMonitors in the specified namespace."""
    return get_kubectl_output(["kubectl", "get", "servicemonitor", "-n", namespace, "-o", "json"])

def get_services(namespace):
    """Fetch all Services in the specified namespace."""
    return get_kubectl_output(["kubectl", "get", "service", "-n", namespace, "-o", "json"])

def find_service_monitor_for_service(service_monitors, service):
    """Match service with its ServiceMonitor based on labels."""
    service_labels = service.get("metadata", {}).get("labels", {})
    for monitor in service_monitors.get("items", []):
        selector = monitor.get("spec", {}).get("selector", {}).get("matchLabels", {})
        if all(service_labels.get(key) == value for key, value in selector.items()):
            return monitor
    return None

def find_port_number(service, port_name):
    """Find the numeric port value based on the port name in a service."""
    for port in service.get("spec", {}).get("ports", []):
        if port.get("name") == port_name:
            return port.get("port")
    return None

def servicemonitorcheckmain(env):

    # Fetch the namespace and desired keywords from environment variables
    namespace = env['namespace'] 
    keywords = env['keywords']
    desired_keywords = keywords.split(',')

    service_monitors = get_service_monitors(namespace)
    services = get_services(namespace)

    responsive_endpoints = []
    missing_ports = []
    no_monitor = []
    curl_errors = []

    if not service_monitors or not services:
        print("Failed to retrieve services or service monitors.")
        return

    for service in services.get("items", []):
        service_name = service.get("metadata", {}).get("name")
        if any(keyword in service_name for keyword in desired_keywords):
            service_monitor = find_service_monitor_for_service(service_monitors, service)
            if not service_monitor:
                no_monitor.append(f"No matching ServiceMonitor for service {service_name}")
                continue

            for endpoint in service_monitor.get("spec", {}).get("endpoints", []):
                port_name = endpoint.get("port")
                port_number = find_port_number(service, port_name)
                if port_number is None:
                    missing_ports.append(f"Port '{port_name}' not found in service {service_name}.")
                    continue

                metrics_path = endpoint.get("path", "/metrics")
                curl_cmd = f"curl -s -I http://{service_name}.{namespace}:{port_number}{metrics_path}"
                try:
                    curl_output = subprocess.check_output(curl_cmd.split(), stderr=subprocess.STDOUT).decode("utf-8")
                    if "HTTP/1.1 200 OK" in curl_output:
                        responsive_endpoints.append(f"Metrics endpoint {metrics_path} for service {service_name} is responsive.")
                    else:
                        curl_errors.append(f"Metrics endpoint {metrics_path} for service {service_name} is not responsive.")
                except subprocess.CalledProcessError as e:
                    curl_errors.append(f"Failed to execute curl command for service {service_name}. Error: {e.output.decode('utf-8')}")

    # Print consolidated results
    if responsive_endpoints:
        print("\nResponsive Endpoints:")
        for line in responsive_endpoints:
            print(line)
    if missing_ports:
        print("\nMissing Ports:")
        for line in missing_ports:
            print(line)
    if no_monitor:
        print("\nNo Service Monitors:")
        for line in no_monitor:
            print(line)
    if curl_errors:
        print("\nCurl Errors:")
        for line in curl_errors:
            print(line)
            
if __name__ == "__main__":
    checkservicemetrics.servicemonitorcheckmain(env=env["servicemonitor"])
