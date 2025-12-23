"""DNS verification utilities for domain ownership validation."""

import hashlib
import logging
import secrets
import socket
from typing import Optional

logger = logging.getLogger(__name__)


def generate_verification_code(domain: str, secret: str = "") -> str:
    """Generate a verification code for a domain.

    Args:
        domain: Domain to generate code for.
        secret: Optional secret for additional entropy.

    Returns:
        Verification code string.
    """
    # Generate a random component
    random_part = secrets.token_hex(16)

    # Create hash of domain + random
    data = f"{domain}:{random_part}:{secret}".encode()
    hash_part = hashlib.sha256(data).hexdigest()[:16]

    return f"shortener-verify={hash_part}"


def verify_domain_dns(domain: str, expected_code: str) -> dict:
    """Verify domain ownership via DNS TXT record.

    The domain owner must add a TXT record with the verification code.

    Args:
        domain: Domain to verify.
        expected_code: Expected verification code.

    Returns:
        Dict with verification result:
        {
            "verified": bool,
            "error": Optional[str],
            "found_records": list
        }
    """
    import dns.resolver
    import dns.exception

    try:
        # Query TXT records for the domain
        answers = dns.resolver.resolve(domain, "TXT")

        found_records = []
        for rdata in answers:
            # TXT records can have multiple strings, join them
            txt_value = "".join(s.decode() if isinstance(s, bytes) else s
                                for s in rdata.strings)
            found_records.append(txt_value)

            # Check if our verification code is present
            if expected_code in txt_value:
                return {
                    "verified": True,
                    "error": None,
                    "found_records": found_records,
                }

        return {
            "verified": False,
            "error": "Verification TXT record not found",
            "found_records": found_records,
        }

    except dns.resolver.NXDOMAIN:
        return {
            "verified": False,
            "error": "Domain does not exist",
            "found_records": [],
        }
    except dns.resolver.NoAnswer:
        return {
            "verified": False,
            "error": "No TXT records found for domain",
            "found_records": [],
        }
    except dns.resolver.NoNameservers:
        return {
            "verified": False,
            "error": "No nameservers available for domain",
            "found_records": [],
        }
    except dns.exception.Timeout:
        return {
            "verified": False,
            "error": "DNS query timed out",
            "found_records": [],
        }
    except Exception as e:
        logger.error(f"DNS verification error for {domain}: {e}")
        return {
            "verified": False,
            "error": f"DNS lookup failed: {str(e)}",
            "found_records": [],
        }


def verify_domain_cname(domain: str, expected_target: str) -> dict:
    """Verify domain CNAME points to our service.

    Args:
        domain: Domain to verify.
        expected_target: Expected CNAME target (e.g., "redirect.shortener.io").

    Returns:
        Dict with verification result.
    """
    import dns.resolver
    import dns.exception

    try:
        answers = dns.resolver.resolve(domain, "CNAME")

        for rdata in answers:
            target = str(rdata.target).rstrip(".")
            if target == expected_target or target.endswith(f".{expected_target}"):
                return {
                    "verified": True,
                    "error": None,
                    "cname_target": target,
                }

        return {
            "verified": False,
            "error": f"CNAME does not point to {expected_target}",
            "cname_target": str(answers[0].target).rstrip(".") if answers else None,
        }

    except dns.resolver.NoAnswer:
        # No CNAME, check if A record points to us
        return verify_domain_a_record(domain, expected_target)
    except dns.resolver.NXDOMAIN:
        return {
            "verified": False,
            "error": "Domain does not exist",
            "cname_target": None,
        }
    except Exception as e:
        logger.error(f"CNAME verification error for {domain}: {e}")
        return {
            "verified": False,
            "error": f"DNS lookup failed: {str(e)}",
            "cname_target": None,
        }


def verify_domain_a_record(domain: str, our_hostname: str) -> dict:
    """Verify domain A record points to our IP.

    Args:
        domain: Domain to verify.
        our_hostname: Our service hostname to resolve for comparison.

    Returns:
        Dict with verification result.
    """
    import dns.resolver
    import dns.exception

    try:
        # Get our IP addresses
        our_ips = set()
        try:
            our_answers = dns.resolver.resolve(our_hostname, "A")
            our_ips = {str(rdata.address) for rdata in our_answers}
        except Exception:
            # If we can't resolve our own hostname, use socket
            try:
                our_ips = {socket.gethostbyname(our_hostname)}
            except Exception:
                pass

        if not our_ips:
            return {
                "verified": False,
                "error": "Could not determine service IP addresses",
                "domain_ips": [],
            }

        # Get domain's IP addresses
        answers = dns.resolver.resolve(domain, "A")
        domain_ips = {str(rdata.address) for rdata in answers}

        # Check for overlap
        if domain_ips & our_ips:
            return {
                "verified": True,
                "error": None,
                "domain_ips": list(domain_ips),
            }

        return {
            "verified": False,
            "error": f"A record does not point to our IPs ({', '.join(our_ips)})",
            "domain_ips": list(domain_ips),
        }

    except dns.resolver.NXDOMAIN:
        return {
            "verified": False,
            "error": "Domain does not exist",
            "domain_ips": [],
        }
    except dns.resolver.NoAnswer:
        return {
            "verified": False,
            "error": "No A records found",
            "domain_ips": [],
        }
    except Exception as e:
        logger.error(f"A record verification error for {domain}: {e}")
        return {
            "verified": False,
            "error": f"DNS lookup failed: {str(e)}",
            "domain_ips": [],
        }


def get_domain_verification_instructions(domain: str, verification_code: str) -> dict:
    """Get instructions for verifying domain ownership.

    Args:
        domain: Domain to verify.
        verification_code: Verification code to add.

    Returns:
        Dict with verification instructions.
    """
    return {
        "domain": domain,
        "verification_code": verification_code,
        "methods": [
            {
                "type": "txt",
                "name": "TXT Record (Recommended)",
                "instructions": [
                    f"1. Go to your DNS provider's control panel",
                    f"2. Add a new TXT record for '{domain}'",
                    f"3. Set the value to: {verification_code}",
                    f"4. Wait for DNS propagation (usually 5-30 minutes)",
                    f"5. Click 'Verify' to complete verification",
                ],
                "record": {
                    "type": "TXT",
                    "name": domain,
                    "value": verification_code,
                },
            },
            {
                "type": "cname",
                "name": "CNAME Record",
                "instructions": [
                    f"1. Go to your DNS provider's control panel",
                    f"2. Add a CNAME record for '{domain}'",
                    f"3. Point it to: redirect.shortener.io",
                    f"4. Wait for DNS propagation",
                    f"5. Click 'Verify' to complete verification",
                ],
                "record": {
                    "type": "CNAME",
                    "name": domain,
                    "value": "redirect.shortener.io",
                },
            },
        ],
    }
