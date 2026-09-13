package hindsight

import (
	"encoding/json"
	"strings"
	"testing"
)

func TestCreateBankRequestObservationScopeWhitelistSerialization(t *testing.T) {
	t.Run("unset is omitted", func(t *testing.T) {
		payload, err := json.Marshal(NewCreateBankRequest())
		if err != nil {
			t.Fatal(err)
		}
		if strings.Contains(string(payload), "observation_scope_tag_key_whitelist") {
			t.Fatalf("unset whitelist should be omitted: %s", payload)
		}
	})

	t.Run("explicit empty list is preserved", func(t *testing.T) {
		request := NewCreateBankRequest()
		request.SetObservationScopeTagKeyWhitelist([]string{})
		payload, err := json.Marshal(request)
		if err != nil {
			t.Fatal(err)
		}
		if !strings.Contains(string(payload), `"observation_scope_tag_key_whitelist":[]`) {
			t.Fatalf("empty whitelist should be serialized: %s", payload)
		}
	})
}
