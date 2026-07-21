package main

import (
	"fmt"
	"log"
	"net/http"
	"time"
)

// Este serviço roda na porta 8080 e o Python faz requisições a ele
// para disparar sincronizações pesadas em Background sem travar a interface.

func syncHandler(w http.ResponseWriter, r *http.Request) {
    // Goroutine dispara o processo sem bloquear
	go func() {
		log.Println("Iniciando sincronização pesada com Hugging Face...")
		// Simula I/O pesado de rede
		time.Sleep(5 * time.Second) 
		log.Println("Sincronização do DB e Arquivos BIN concluída.")
	}()
	
	w.WriteHeader(http.StatusAccepted)
	fmt.Fprintf(w, `{"status": "Sincronização em Background Iniciada"}`)
}

func main() {
	http.HandleFunc("/api/sync", syncHandler)
	log.Println("HyperTork Go Sync Service rodando na porta 8080...")
	log.Fatal(http.ListenAndServe(":8080", nil))
}