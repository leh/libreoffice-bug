#!/usr/bin/env python3
"""Dispatch AcceptAllTrackedChanges through a standalone office's UNO socket."""
import argparse
import configparser
import json
import os
from pathlib import Path
import sys
import time
import traceback

import uno
import pyuno
from com.sun.star.beans import PropertyValue
from com.sun.star.connection import NoConnectException

STARTED = time.monotonic()


def event(phase, **details):
    print(json.dumps({"phase": phase, "seconds": round(time.monotonic() - STARTED, 6), **details}), flush=True)


def prop(name, value):
    result = PropertyValue()
    result.Name = name
    result.Value = value
    return result


def implementation(component):
    return component.getImplementationName() if component is not None else None


def document_state(document):
    names = ("ShowChanges", "RedlineDisplayType", "RecordChanges")
    info = document.getPropertySetInfo()
    return {name: document.getPropertyValue(name) for name in names if info.hasPropertyByName(name)}


def office_processes():
    result = []
    for process_dir in Path("/proc").glob("[0-9]*"):
        try:
            executable = str((process_dir / "exe").readlink())
            if "soffice" in executable or "python.bin" in executable or "oosplash" in executable:
                result.append({"pid": int(process_dir.name), "executable": executable,
                               "command": (process_dir / "cmdline").read_bytes().replace(b"\0", b" ").decode()})
        except (OSError, UnicodeDecodeError):
            pass
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("--hidden", choices=("true", "false"), default="true")
    parser.add_argument("--mode", choices=("accept", "macro", "export-only"), default="accept")
    parser.add_argument("--port", type=int, default=2002)
    parser.add_argument("--show-changes", choices=("preserve", "false"), default="preserve")
    args = parser.parse_args()
    version = configparser.ConfigParser()
    version.read("/opt/libreoffice26.8/program/versionrc")
    event("client.start", pid=os.getpid(), executable=sys.executable, python=sys.version,
          uno_path=uno.__file__, pyuno_path=pyuno.__file__,
          buildid=version["Version"]["buildid"], hidden=args.hidden, mode=args.mode, show_changes_request=args.show_changes, processes=office_processes())
    local_context = uno.getComponentContext()
    resolver = local_context.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local_context)
    remote_url = f"uno:socket,host=127.0.0.1,port={args.port};urp;StarOffice.ComponentContext"
    event("connect.begin", url=remote_url)
    deadline = time.monotonic() + 10
    while True:
        try:
            context = resolver.resolve(remote_url)
            break
        except NoConnectException:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.05)
    service_manager = context.ServiceManager
    desktop = service_manager.createInstanceWithContext("com.sun.star.frame.Desktop", context)
    configuration_provider = service_manager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", context)
    configuration = configuration_provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationAccess", (prop("nodepath", "/org.openoffice.Setup/Product"),))
    event("connect.ok", product=configuration.getPropertyValue("ooName"),
          version=configuration.getPropertyValue("ooSetupVersionAboutBox"))
    event("load.begin", input=args.input)
    document = desktop.loadComponentFromURL(uno.systemPathToFileUrl(str(Path(args.input).resolve())), "_blank", 0,
                                            (prop("Hidden", args.hidden == "true"), prop("ReadOnly", False)))
    if document is None:
        raise RuntimeError("loadComponentFromURL returned no document")
    event("load.ok", implementation=implementation(document), redlines=document.getRedlines().getCount(),
          show_changes=document.getPropertyValue("ShowChanges"), document_state=document_state(document))
    controller = document.getCurrentController()
    if controller is None:
        raise RuntimeError("No current controller")
    frame = controller.getFrame()
    if frame is None:
        raise RuntimeError("No controller frame")
    event("controller.ok", implementation=implementation(controller), frame_implementation=implementation(frame),
          frame_container_visible=frame.getContainerWindow().isVisible(),
          show_changes=document.getPropertyValue("ShowChanges"), redlines=document.getRedlines().getCount(),
          document_state=document_state(document), view_settings_implementation=implementation(controller.getViewSettings()))
    view_settings = controller.getViewSettings()
    interesting_view_properties = {}
    for item in view_settings.getPropertySetInfo().getProperties():
        if any(word in item.Name.lower() for word in ("redline", "change", "insert", "delet")):
            try:
                interesting_view_properties[item.Name] = repr(view_settings.getPropertyValue(item.Name))
            except Exception as error:
                interesting_view_properties[item.Name] = f"{type(error).__name__}: {error}"
    event("view-properties", properties=interesting_view_properties)
    if args.show_changes == "false":
        event("show-changes.begin", requested=False, before=document_state(document))
        # The getter reports RedlineFlags, while the setter uses SetHideRedlines.
        # Record both rather than assuming the getter must become false.
        document.setPropertyValue("ShowChanges", False)
        event("show-changes.ok", after=document_state(document))
    if args.mode in ("accept", "macro"):
        dispatcher = service_manager.createInstanceWithContext("com.sun.star.frame.DispatchHelper", context)
        event("accept-changes.begin", command=".uno:AcceptAllTrackedChanges", route=args.mode)
        phase_started = time.monotonic()
        if args.mode == "accept":
            dispatcher.executeDispatch(frame, ".uno:AcceptAllTrackedChanges", "", 0, ())
        else:
            factory = service_manager.createInstanceWithContext("com.sun.star.script.provider.MasterScriptProviderFactory", context)
            provider = factory.createScriptProvider("")
            script = provider.getScript("vnd.sun.star.script:Standard.Repro.AcceptChanges?language=Basic&location=application")
            event("macro.invoke.begin", script="Standard.Repro.AcceptChanges")
            script.invoke((), (), ())
            event("macro.invoke.ok")
        event("accept-changes.ok", operation_seconds=round(time.monotonic() - phase_started, 6),
              redlines=document.getRedlines().getCount(), show_changes=document.getPropertyValue("ShowChanges"), document_state=document_state(document))
        if document.getRedlines().getCount() != 0:
            raise RuntimeError("The dispatch returned without accepting all tracked changes")
    event("export.begin", output=args.output)
    phase_started = time.monotonic()
    document.storeToURL(uno.systemPathToFileUrl(str(Path(args.output).resolve())),
                        (prop("FilterName", "writer_pdf_Export"), prop("Overwrite", True)))
    output = Path(args.output)
    if not output.is_file() or not output.read_bytes().startswith(b"%PDF-"):
        raise RuntimeError("Export did not create a PDF file")
    event("export.ok", operation_seconds=round(time.monotonic() - phase_started, 6), bytes=output.stat().st_size,
          header=output.read_bytes()[:8].decode("ascii"))
    event("close.begin")
    document.close(True)
    event("close.ok")
    desktop.terminate()
    event("done")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        event("error", error_type=type(error).__name__, message=str(error))
        traceback.print_exc()
        raise
