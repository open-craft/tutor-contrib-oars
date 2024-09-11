# Superset image with additional database drivers
# https://hub.docker.com/r/apache/superset
# https://github.com/apache/superset/releases
# https://github.com/apache/superset/blob/master/Dockerfile
# https://superset.apache.org/docs/databases/installing-database-drivers
FROM apache/superset:4.1.0rc2

USER root

COPY ./requirements.txt /app/requirements.txt
COPY ./localization/compile_translations.py /app/localization/compile_translations.py
COPY ./localization/datasets_strings.yaml /app/localization/datasets_strings.yaml

RUN pip install -r /app/requirements.txt

# Extracted from https://superset.apache.org/docs/installation/alerts-reports/#custom-dockerfile
# https://github.com/apache/superset/blob/3.0.0/Dockerfile#L118-L132
ARG GECKODRIVER_VERSION=v0.33.0
ARG FIREFOX_VERSION=117.0.1

RUN apt-get update -q \
    && apt-get install -yq --no-install-recommends \
        git \
        libnss3 \
        libdbus-glib-1-2 \
        libgtk-3-0 \
        libx11-xcb1 \
        libasound2 \
        libxtst6 \
        wget \
    # Install GeckoDriver WebDriver
    && wget https://github.com/mozilla/geckodriver/releases/download/${GECKODRIVER_VERSION}/geckodriver-${GECKODRIVER_VERSION}-linux64.tar.gz -O - | tar xfz - -C /usr/local/bin \
    # Install Firefox
    && wget https://download-installer.cdn.mozilla.net/pub/firefox/releases/${FIREFOX_VERSION}/linux-x86_64/en-US/firefox-${FIREFOX_VERSION}.tar.bz2 -O - | tar xfj - -C /opt \
    && ln -s /opt/firefox/firefox /usr/local/bin/firefox \
    && apt-get autoremove -yqq --purge wget && rm -rf /var/lib/apt/lists/* /var/[log,tmp]/* /tmp/* && apt-get clean

COPY ./openedx-assets /app/openedx-assets

# Pull latest aspects translations from openedx-tranlsations repository
RUN atlas pull translations/tutor-contrib-aspects/tutoraspects/templates/aspects/apps/superset/conf/locale:/app/localization/

# combine the /app/localization/ files into a single `localization/locale.yaml` file in a way Aspects can use
RUN python /app/localization/compile_translations.py

USER superset
