package com.nullxoid.nullbridge.crypto.agent

import org.junit.Assert.*
import org.junit.Test

class AccountLinkContractTest {
    private class Fixture {
        var now = 1000L
        val endpoint = mapOf<String, Any?>("conversation" to "a".repeat(32), "publicKey" to "retained-key")
        val challenge = mapOf("purpose" to AgentAccountLink.PROOF, "version" to 1L,
            "issuer" to "https://suite.example", "endpoint" to endpoint, "nonce" to "b".repeat(64),
            "issuedAt" to now, "expiresAt" to now + 300)
        val saved = mapOf("ticket" to "c".repeat(64), "challenge" to challenge, "grantsPermissions" to false)
        var consent: Map<String, Any?> = mapOf("purpose" to AgentAccountLink.CONSENT, "version" to 1L,
            "binding" to "d".repeat(64), "account" to mapOf("issuer" to "https://suite.example", "userId" to "artistic-id", "username" to "artistic"),
            "expiresAt" to now + 120, "endpoint" to endpoint, "nonce" to "e".repeat(64))
        var response: Map<String, Any?>? = null
        val calls = mutableListOf<String>()
        val signed = mutableListOf<String>()
        val client = AgentAccountLink(endpoint, "https://suite.example", { now }, { action, _ ->
            calls.add(action)
            response ?: when (action) {
                "begin" -> saved
                "prove" -> mapOf("proved" to true, "expiresAt" to now + 300, "grantsPermissions" to false)
                "consent-review", "consent-prove" -> mapOf("challenge" to consent, "confirmed" to (action == "consent-prove"), "grantsPermissions" to false)
                else -> error("unexpected route")
            }
        }, { signed.add(String(it, Charsets.US_ASCII)); "signature" })
    }
    private fun rejected(action: () -> Unit) { assertThrows(IllegalArgumentException::class.java, action) }

    @Test fun provesRetainedEndpointThenConfirmsExactAccount() {
        val f = Fixture(); val saved = f.client.begin(); val pending = f.client.prove(saved)
        assertEquals(300L, pending.remainingSeconds)
        val review = f.client.review(saved); val shown = f.client.reviewedState(saved, review)
        assertEquals("artistic", shown.username); assertFalse(shown.confirmed)
        assertEquals(120L, shown.remainingSeconds)
        assertTrue(f.client.confirm(saved, review).confirmed)
        assertEquals(listOf("begin", "prove", "consent-review", "consent-review", "consent-prove"), f.calls)
        assertTrue(f.signed[0].startsWith(AgentAccountLink.PROOF + "\n"))
        assertTrue(f.signed[1].startsWith(AgentAccountLink.CONSENT + "\n"))
    }
    @Test fun rejectsChangedEndpointBeforeSigning() {
        val f = Fixture()
        f.response = f.saved + ("challenge" to (f.challenge + ("endpoint" to (f.endpoint + ("publicKey" to "replacement")))))
        rejected { f.client.begin() }; assertTrue(f.signed.isEmpty())
    }
    @Test fun rejectsChangedIssuerBeforeSigning() {
        val f = Fixture(); f.response = f.saved + ("challenge" to (f.challenge + ("issuer" to "https://other.example")))
        rejected { f.client.begin() }; assertTrue(f.signed.isEmpty())
    }
    @Test fun cannotConfirmDifferentAccountThanReviewed() {
        val f = Fixture(); val reviewed = f.client.review(f.saved)
        f.consent = f.consent + ("account" to mapOf("issuer" to "https://suite.example", "userId" to "other", "username" to "admin"))
        rejected { f.client.confirm(f.saved, reviewed) }; assertFalse(f.calls.contains("consent-prove")); assertTrue(f.signed.isEmpty())
    }
    @Test fun expiredSetupNeverSignsOrSendsConfirmation() {
        val f = Fixture(); val reviewed = f.client.review(f.saved); f.now = 1300L
        rejected { f.client.confirm(f.saved, reviewed) }; assertTrue(f.signed.isEmpty())
    }
    @Test fun consentCannotExtendTheSetupDeadline() {
        val f = Fixture(); f.consent = f.consent + ("expiresAt" to 1301L)
        rejected { f.client.review(f.saved) }; assertTrue(f.signed.isEmpty())
    }
    @Test fun linkCannotClaimFilePermission() {
        val f = Fixture(); f.response = f.saved + ("grantsPermissions" to true)
        rejected { f.client.begin() }
    }
    @Test fun resumeUsesSameTicketAndKeyProof() {
        val f = Fixture(); val saved = f.client.begin()
        assertEquals(f.client.prove(saved).ticket, f.client.prove(saved).ticket)
        assertEquals(f.signed[0], f.signed[1]); assertEquals(1, f.calls.count { it == "begin" })
    }
}
