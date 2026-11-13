#define _GNU_SOURCE
#include <stdbool.h>
#include <stdint.h>
#include <LibreOfficeKit/LibreOfficeKitInit.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <sys/stat.h>
#include <pthread.h>

static double started;
static double now(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec / 1000000000.0;
}
static void stage(const char *name) {
    fprintf(stderr, "[LOK-REPRO] %.3f %s\n", now() - started, name);
    fflush(stderr);
}
static void failure(LibreOfficeKit *office, const char *operation) {
    char *error = office->pClass->getError(office);
    fprintf(stderr, "[LOK-REPRO] %s: %s\n", operation, error ? error : "no error message");
    if (error) office->pClass->freeError(error);
}
static void callback(int type, const char *payload, void *data) {
    LibreOfficeKit *office = data;
    /* Abort a password request without a dialog if no password is available. */
    if (type == 20) office->pClass->setDocumentPassword(office, payload, NULL);
}
struct LoadTask {
    LibreOfficeKit *office;
    const char *url;
    const char *options;
    LibreOfficeKitDocument *document;
};
static void *load_on_thread(void *data) {
    struct LoadTask *task = data;
    task->document = task->office->pClass->documentLoadWithOptions(task->office, task->url, task->options);
    return NULL;
}
int main(int argc, char **argv) {
    if (argc != 3) {
        fprintf(stderr, "Usage: %s /absolute/input.docx /absolute/output.pdf\n", argv[0]);
        return 64;
    }
    started = now();
    char profile[] = "/tmp/native-lok-profile-XXXXXX";
    if (!mkdtemp(profile)) { perror("mkdtemp"); return 1; }
    /* Use a private input copy for each run to avoid existing lock files. */
    char work[] = "/tmp/native-lok-input-XXXXXX";
    if (!mkdtemp(work)) { perror("mkdtemp input"); return 1; }
    char input_copy[512];
    snprintf(input_copy, sizeof(input_copy), "%s/input.docx", work);
    FILE *source = fopen(argv[1], "rb");
    FILE *target = fopen(input_copy, "wb");
    if (!source || !target) { perror("input copy"); return 1; }
    char buffer[8192];
    size_t count;
    while ((count = fread(buffer, 1, sizeof(buffer), source)) > 0) {
        if (fwrite(buffer, 1, count, target) != count) return 1;
    }
    if (ferror(source)) return 1;
    fclose(source);
    if (fclose(target)) return 1;
    char profile_url[512], input_url[4096], output_url[4096];
    const char *profile_path = getenv("LOK_PROFILE_PATH");
    snprintf(profile_url, sizeof(profile_url), "file://%s", profile_path ? profile_path : profile);
    snprintf(input_url, sizeof(input_url), "file://%s", input_copy);
    snprintf(output_url, sizeof(output_url), "file://%s", argv[2]);
    const char *program = getenv("LOK_PROGRAM_PATH");
    if (!program) program = "/usr/lib/libreoffice/program";
    const char *options = getenv("LOK_LOAD_OPTIONS");
    if (!options) options = "Batch=true,EnableMacrosExecution=true,MacroSecurityLevel=3";
    if (getenv("LOK_PREPARE_PROFILE")) {
        char command[2048];
        snprintf(command, sizeof(command), "%s/soffice --headless --nologo --norestore --terminate_after_init -env:UserInstallation=%s", program, profile_url);
        if (system(command) != 0) return 2;
    }
    stage("init.begin");
    LibreOfficeKit *office = lok_init_2(program, profile_url);
    if (!office) { stage("init.failed"); return 2; }
    stage("init.ok");
    if (getenv("LOK_REGISTER_CALLBACK")) {
        office->pClass->registerCallback(office, callback, office);
        office->pClass->setOptionalFeatures(office, 1ULL);
    }
    stage("load.begin");
    struct LoadTask task = { office, input_url, options, NULL };
    if (getenv("LOK_LOAD_THREAD")) {
        pthread_t worker;
        if (pthread_create(&worker, NULL, load_on_thread, &task)) return 6;
        pthread_join(worker, NULL);
    } else {
        load_on_thread(&task);
    }
    LibreOfficeKitDocument *document = task.document;
    if (!document) { failure(office, "load.failed"); return 3; }
    stage("load.ok");
    const char *macro = getenv("LOK_RUN_MACRO");
    if (macro) {
        stage("accept-changes.begin");
        if (!office->pClass->runMacro(office, macro)) {
            failure(office, "accept-changes.failed"); return 7;
        }
        stage("accept-changes.ok");
    }
    stage("save.begin");
    int ok = document->pClass->saveAs(document, output_url, "pdf", NULL);
    if (!ok) { failure(office, "save.failed"); return 4; }
    stage("save.ok");
    struct stat st;
    if (stat(argv[2], &st) != 0 || st.st_size == 0) { stage("pdf.missing"); return 5; }
    fprintf(stderr, "[LOK-REPRO] PDF: %lld bytes\n", (long long)st.st_size);
    /* Process exit releases all resources and isolates subsequent runs. */
    fflush(NULL);
    _exit(0);
}
