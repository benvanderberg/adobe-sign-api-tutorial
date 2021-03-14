import os
import requests
from flask import Flask, render_template, request, url_for
from dotenv import load_dotenv


load_dotenv()
app = Flask(__name__)


def sign_validate(resp, code=200):
    if resp.status_code != code:
        raise Exception(
            {
                "issue": "Bad Response",
                "status_code": resp.status_code,
                "data": resp.text,
            }
        )


def headers():
    token = os.getenv("INTEGRATION_KEY")
    return {"Authorization": f"Bearer {token}"}


def base():
    # Send request
    url = "https://api.na1.echosign.com:443/api/rest/v6/baseUris"
    resp = requests.get(url, headers=headers())

    # Validate
    sign_validate(resp)

    data = resp.json()
    return data["apiAccessPoint"]


# ##############################################################################
# HTML
# ##############################################################################


@app.route("/")
def index():
    return render_template("index.html", action="/submitted", method="POST", email=True)


@app.route("/submitted", methods=["POST"])
def submitted():
    data = dict(request.form)
    app.logger.debug(data)
    return render_template("submitted.html", data=data)


# ##############################################################################
# WEBFORM
# ##############################################################################


@app.route("/webform")
def webform_index():
    return render_template(
        "index.html", action="/webform/sign", method="GET", email=False
    )


@app.route("/webform/sign", methods=["GET"])
def webform_sign():
    url = os.getenv("WAIVER_WEBFORM")
    app.logger.debug(url)

    # Build webform URL
    data = dict(request.args)
    if data:
        params = []
        for key, val in data.items():
            params.append(f"{key}={val}")
        query = "&".join(params)
        url = f"{url}#{query}"
    app.logger.debug(url)

    return render_template("sign.html", url=url)


# ##############################################################################
# Send
# ##############################################################################


@app.route("/send")
def send_index():
    return render_template(
        "index.html", action="/send/submitted", method="POST", email=True
    )


@app.route("/send/submitted", methods=["POST"])
def send_submitted():
    data = dict(request.form)
    app.logger.debug(data)

    # Build URL
    url = f"{base()}api/rest/v6/agreements"

    # Payload
    req = {
        "fileInfos": [{"libraryDocumentId": os.getenv("WAIVER_TEMPLATE")}],
        "name": "Waiver",
        "participantSetsInfo": [
            {
                "memberInfos": [{"email": data.get("email")}],
                "order": 1,
                "role": "SIGNER",
            },
            {
                "memberInfos": [{"email": os.getenv("ADMIN")}],
                "order": 2,
                "role": "SIGNER",
            },
        ],
        "signatureType": "ESIGN",
        "state": "IN_PROCESS",
        "mergeFieldInfo": [
            {"fieldName": "firstName", "defaultValue": data.get("firstName")},
            {"fieldName": "lastName", "defaultValue": data.get("lastName")},
        ],
    }

    # Send request
    resp = requests.post(url, headers=headers(), json=req)

    # Validate
    sign_validate(resp, code=201)

    return render_template("submitted.html", data=resp.json())


# ##############################################################################
# Embed
# ##############################################################################


@app.route("/embed")
def embed_index():
    return render_template(
        "index.html", action="/embed/sign", method="POST", email=True
    )


@app.route("/embed/sign", methods=["POST"])
def embed_sign():
    data = dict(request.form)
    app.logger.debug(data)

    # Build URL
    url = f"{base()}api/rest/v6/agreements"
    print(url_for("embed_submitted"))
    # Payload
    req = {
        "fileInfos": [{"libraryDocumentId": os.getenv("WAIVER_TEMPLATE")}],
        "name": "Waiver",
        "participantSetsInfo": [
            {
                "memberInfos": [{"email": data.get("email")}],
                "order": 1,
                "role": "SIGNER",
            },
            {
                "memberInfos": [{"email": os.getenv("ADMIN")}],
                "order": 2,
                "role": "SIGNER",
            },
        ],
        "signatureType": "ESIGN",
        "state": "IN_PROCESS",
        "mergeFieldInfo": [
            {"fieldName": "firstName", "defaultValue": data.get("firstName")},
            {"fieldName": "lastName", "defaultValue": data.get("lastName")},
        ],
        # New Stuff
        "emailOption": {
            "sendOptions": {
                "initEmails": "NONE",
            }
        },
        "postSignOption": {
            "redirectDelay": 0,
            "redirectUrl": url_for("embed_submitted", _external=True),
        },
    }

    # Send request
    resp = requests.post(url, headers=headers(), json=req)
    sign_validate(resp, code=201)

    agreement_data = resp.json()
    agreement_id = agreement_data["id"]

    # Build embed URL
    embed_url = f"{base()}api/rest/v6/agreements/{agreement_id}/signingUrls"

    embed_resp = requests.get(embed_url, headers=headers())
    sign_validate(embed_resp)

    embed_data = embed_resp.json()
    signing_url = embed_data["signingUrlSetInfos"][0]["signingUrls"][0]["esignUrl"]

    return render_template("sign.html", url=signing_url)


@app.route("/embed/submitted", methods=["GET"])
def embed_submitted():
    return "<h2>Successfully submitted</h2>"
